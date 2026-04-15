const fs = require('fs');
const Groq = require("groq-sdk");
const config = require("./config");
const actionHandler = require("./action_handler");

const groq = new Groq({ apiKey: config.GROQ_API_KEY });

const tools = [
    {
        type: "function",
        function: {
            name: "open_application",
            description: "Opens a specific application on the user's Windows computer.",
            parameters: {
                type: "object",
                properties: { app_name: { type: "string" } },
                required: ["app_name"]
            }
        }
    },
    {
        type: "function",
        function: {
            name: "search_web",
            description: "Searches the web for a given query and opens the browser.",
            parameters: {
                type: "object",
                properties: { query: { type: "string" } },
                required: ["query"]
            }
        }
    },
    {
        type: "function",
        function: {
            name: "lock_screen",
            description: "Locks the user's computer screen.",
            parameters: { type: "object", properties: {} }
        }
    },
    {
        type: "function",
        function: {
            name: "get_current_time",
            description: "Retrieves the current date and time of the system.",
            parameters: { type: "object", properties: {} }
        }
    }
];

// Ephemeral Context RAM - Resets when the app closes
let messages = [
    { role: "system", content: config.SYSTEM_PROMPT }
];

async function transcribeAudio(audioPath) {
    try {
        const transcription = await groq.audio.transcriptions.create({
            file: fs.createReadStream(audioPath),
            model: "whisper-large-v3", 
            language: "en",
        });
        return transcription.text.trim();
    } catch (error) {
        console.error("[Groq STT Error]", error.message);
        return null;
    }
}

async function processPrompt(userText) {
    try {
        // Manage context length so it doesn't overflow Groq's limits over long sessions
        if (messages.length > 20) {
            // Keep the system prompt, but remove older conversation turns
            messages.splice(1, 2); 
        }

        messages.push({ role: "user", content: userText });

        const response = await groq.chat.completions.create({
            model: config.GROQ_MODEL,
            messages: messages,
            tools: tools,
            tool_choice: "auto",
            max_tokens: 150,
            temperature: 0.5
        });

        const responseMessage = response.choices[0].message;
        const toolCalls = responseMessage.tool_calls;

        if (toolCalls && toolCalls.length > 0) {
            const toolCall = toolCalls[0]; 
            const functionName = toolCall.function.name;
            const args = toolCall.function.arguments ? JSON.parse(toolCall.function.arguments) : {};
            
            let actionResult;
            
            if (functionName === "open_application") {
                actionResult = await actionHandler.openApplication(args.app_name);
            } else if (functionName === "search_web") {
                actionResult = await actionHandler.searchWeb(args.query);
            } else if (functionName === "lock_screen") {
                actionResult = await actionHandler.lockScreen();
            } else if (functionName === "get_current_time") {
                actionResult = actionHandler.getCurrentTime();
                
                messages.push(responseMessage);
                messages.push({
                    role: "tool",
                    tool_call_id: toolCall.id,
                    name: functionName,
                    content: JSON.stringify(actionResult)
                });
                
                const followUpResponse = await groq.chat.completions.create({
                    model: config.GROQ_MODEL,
                    messages: messages,
                    max_tokens: 100
                });
                
                const finalMsg = followUpResponse.choices[0].message;
                messages.push(finalMsg); // Save final response to context
                return finalMsg.content;
            }

            // Save the action confirmation to the context memory
            messages.push(responseMessage);
            messages.push({
                role: "tool",
                tool_call_id: toolCall.id,
                name: functionName,
                content: JSON.stringify(actionResult)
            });

            // Return the direct execution string to the user
            return actionResult.message;
        }

        if (responseMessage.content) {
            messages.push(responseMessage); // Save conversational response to context memory
            return responseMessage.content;
        }

        return "I processed the request, but have no response.";
    } catch (error) {
        console.error("[Groq LLM Error]", error.message);
        return "My brain is currently disconnected.";
    }
}

async function synthesizeSpeech(text, outputPath) {
    try {
        const response = await groq.audio.speech.create({
            model: "canopylabs/orpheus-v1-english", 
            voice: "autumn", 
            input: text,
            response_format: "wav"
        });
        
        const buffer = Buffer.from(await response.arrayBuffer());
        fs.writeFileSync(outputPath, buffer);
        return true;
    } catch (error) {
        console.error("[Groq TTS Error]", error.message);
        return false;
    }
}

module.exports = {
    transcribeAudio,
    processPrompt,
    synthesizeSpeech
};