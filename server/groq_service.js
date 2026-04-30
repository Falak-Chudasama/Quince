const fs = require('fs');
const axios = require('axios');
const Groq = require("groq-sdk");
const config = require("./config");
const actionHandler = require("./action_handler");
const path = require('path');

const groq = new Groq({ apiKey: config.GROQ_API_KEY });

// ==========================================
// RAG MEMORY HELPERS (Ultra-Fast HTTP)
// ==========================================
async function addMemory(role, text) {
    try {
        await axios.post('http://127.0.0.1:8001/add', { role: role, text: text });
    } catch (e) {
        // Silently fail if server is unreachable
    }
}

async function getMemoryContext(text) {
    try {
        const response = await axios.post('http://127.0.0.1:8001/query', { text: text, role: "system" });
        return response.data.context.trim();
    } catch (e) { 
        return ""; 
    }
}

// ==========================================
// TOOLS DEFINITION
// ==========================================
const tools = [
    {
        type: "function",
        function: {
            name: "analyze_screen",
            description: "Takes a live screenshot. Use this ONLY when the user explicitly asks what is on their screen, what they are looking at, or to read an error on the screen.",
            parameters: { type: "object", properties: {} }
        }
    },
    { type: "function", function: { name: "open_application", description: "Opens an application.", parameters: { type: "object", properties: { app_name: { type: "string" } }, required: ["app_name"] } } },
    { type: "function", function: { name: "search_web", description: "Searches the web.", parameters: { type: "object", properties: { query: { type: "string" } }, required: ["query"] } } },
    { type: "function", function: { name: "lock_screen", description: "Locks the screen.", parameters: { type: "object", properties: {} } } },
    { type: "function", function: { name: "get_current_time", description: "Retrieves the date and time.", parameters: { type: "object", properties: {} } } }
];

let messages = [{ role: "system", content: config.SYSTEM_PROMPT }];

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

async function processPrompt(userText, mode) {
    try {
        // 1. Context Injection (Ultra-Fast RAG via HTTP)
        const pastContext = await getMemoryContext(userText);
        let contextualPrompt = userText;
        if (pastContext) {
            contextualPrompt = `[Context from past conversation:\n${pastContext}]\n\nCurrent User Request: ${userText}`;
        }

        // 2. Save pure request to Memory
        await addMemory("user", userText);

        let finalResponseText = "";

        // ==========================================
        // LOCAL MODE (OLLAMA + QWEN)
        // ==========================================
        if (mode === "local") {
            const isAskingAboutScreen = /screen|look|see|what is this|error/i.test(userText);
            let payload = {
                model: "qwen2.5-vl", 
                messages: [{ role: "user", content: contextualPrompt }],
                stream: false
            };

            if (isAskingAboutScreen) {
                const screenData = await actionHandler.captureScreen();
                if (screenData.success) {
                    payload.messages[0].images = [screenData.base64];
                }
            }

            const response = await axios.post('http://localhost:11434/api/chat', payload);
            finalResponseText = response.data.message.content;
        }
        
        // ==========================================
        // CLOUD MODE (GROQ)
        // ==========================================
        else {
            if (messages.length > 20) messages.splice(1, 2); 
            messages.push({ role: "user", content: contextualPrompt });

            const response = await groq.chat.completions.create({
                model: config.GROQ_MODEL,
                messages: messages,
                tools: tools,
                tool_choice: "auto",
                max_completion_tokens: 150,
                temperature: 0.5
            });

            const responseMessage = response.choices[0].message;
            const toolCalls = responseMessage.tool_calls;

            if (toolCalls && toolCalls.length > 0) {
                const toolCall = toolCalls[0]; 
                const functionName = toolCall.function.name;
                const args = toolCall.function.arguments ? JSON.parse(toolCall.function.arguments) : {};
                let actionResult;
                
                // --- VISION API INTEGRATION ---
                if (functionName === "analyze_screen") {
                    const screenData = await actionHandler.captureScreen();
                    if (!screenData.success) return screenData.message;

                    messages.push(responseMessage);
                    messages.push({ role: "tool", tool_call_id: toolCall.id, name: functionName, content: "Screenshot captured." });

                    // Utilizing Llama 4 Scout 17B for powerful, multi-turn multimodal capabilities
                    const visionResponse = await groq.chat.completions.create({
                        model: "meta-llama/llama-4-scout-17b-16e-instruct",
                        messages: [
                            { role: "system", content: "You are Quince, a helpful desktop assistant. Describe the visual input concisely to aid the user." },
                            { role: "user", content: [
                                { type: "text", text: `Analyze this screenshot to answer the user's request: "${userText}"` },
                                { type: "image_url", image_url: { url: `data:image/jpeg;base64,${screenData.base64}` } }
                            ]}
                        ],
                        max_completion_tokens: 500
                    });

                    finalResponseText = visionResponse.choices[0].message.content;
                    messages.push({ role: "assistant", content: finalResponseText });
                } 
                // --- STANDARD TOOLS ---
                else {
                    if (functionName === "open_application") actionResult = await actionHandler.openApplication(args.app_name);
                    else if (functionName === "search_web") actionResult = await actionHandler.searchWeb(args.query);
                    else if (functionName === "lock_screen") actionResult = await actionHandler.lockScreen();
                    else if (functionName === "get_current_time") actionResult = actionHandler.getCurrentTime();

                    messages.push(responseMessage);
                    messages.push({ role: "tool", tool_call_id: toolCall.id, name: functionName, content: JSON.stringify(actionResult) });

                    const followUpResponse = await groq.chat.completions.create({ model: config.GROQ_MODEL, messages: messages, max_completion_tokens: 150 });
                    finalResponseText = followUpResponse.choices[0].message.content;
                    messages.push({ role: "assistant", content: finalResponseText });
                }
            } else if (responseMessage.content) {
                messages.push(responseMessage); 
                finalResponseText = responseMessage.content;
            } else {
                finalResponseText = "I processed the request, but have no response.";
            }
        }

        // 3. Save Assistant Response to Memory
        await addMemory("quince", finalResponseText);
        
        return finalResponseText;

    } catch (error) {
        console.error("[LLM Error]", error.message);
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
        return false;
    }
}

module.exports = { transcribeAudio, processPrompt, synthesizeSpeech };