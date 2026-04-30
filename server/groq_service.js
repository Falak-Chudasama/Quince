const fs = require('fs');
const axios = require('axios');
const Groq = require("groq-sdk");
const config = require("./config");
const actionHandler = require("./action_handler");
const path = require('path');

const groq = new Groq({ apiKey: config.GROQ_API_KEY });
const LOCAL_API = "http://127.0.0.1:8001";

async function addMemory(role, text) {
    try { await axios.post(`${LOCAL_API}/rag/add`, { role: role, text: text }); } catch (e) {}
}

async function getMemoryContext(text) {
    try {
        const response = await axios.post(`${LOCAL_API}/rag/query`, { text: text, role: "system" });
        return response.data.context.trim();
    } catch (e) { return ""; }
}

// --- UPDATED TOOLS SCHEMA ---
const tools = [
    { type: "function", function: { name: "analyze_screen", description: "Takes a live screenshot. Use this ONLY when the user explicitly asks what is on their screen, what they are looking at, or to read an error on the screen.", parameters: { type: "object", properties: {} } } },
    { 
        type: "function", 
        function: { 
            name: "open_application", 
            description: "Opens an application. Can optionally switch to a specific virtual desktop number (e.g. desktop 2) before opening.", 
            parameters: { 
                type: "object", 
                properties: { 
                    app_name: { type: "string" },
                    desktop_number: { type: "integer", description: "The virtual desktop number to open the app on (1-indexed). Leave blank if the user doesn't specify a desktop." }
                }, 
                required: ["app_name"] 
            } 
        } 
    },
    { type: "function", function: { name: "search_web", description: "Searches the web.", parameters: { type: "object", properties: { query: { type: "string" } }, required: ["query"] } } },
    { type: "function", function: { name: "lock_screen", description: "Locks the screen.", parameters: { type: "object", properties: {} } } }
];

let messages = [{ role: "system", content: config.SYSTEM_PROMPT }];

async function transcribeAudio(audioPath, mode) {
    try {
        if (mode === 'local') {
            const res = await axios.post(`${LOCAL_API}/stt`, { path: audioPath });
            return res.data.text;
        } else {
            const transcription = await groq.audio.transcriptions.create({
                file: fs.createReadStream(audioPath), model: "whisper-large-v3", language: "en",
            });
            return transcription.text.trim();
        }
    } catch (error) { return null; }
}

async function synthesizeSpeech(text, outputPath, mode) {
    try {
        if (mode === 'local') {
            await axios.post(`${LOCAL_API}/tts`, { text: text, output_path: outputPath });
            return true;
        } else {
            const response = await groq.audio.speech.create({
                model: "canopylabs/orpheus-v1-english", voice: "autumn", input: text, response_format: "wav"
            });
            const buffer = Buffer.from(await response.arrayBuffer());
            fs.writeFileSync(outputPath, buffer);
            return true;
        }
    } catch (error) { return false; }
}

async function processPrompt(userText, mode) {
    try {
        const pastContext = await getMemoryContext(userText);
        let contextualPrompt = userText;
        if (pastContext && mode === 'local') {
            contextualPrompt = `[Context:\n${pastContext}]\n\nUser: ${userText}`;
        }
        
        if (mode === 'local') await addMemory("user", userText);

        let finalResponseText = "";

        if (mode === "local") {
            const isAskingAboutScreen = /screen|look|see|what is this|error/i.test(userText);
            let payload = { model: "qwen3-vl:4b", messages: [{ role: "user", content: contextualPrompt }], stream: false };

            if (isAskingAboutScreen) {
                const screenData = await actionHandler.captureScreen();
                if (screenData.success) payload.messages[0].images = [screenData.base64];
            }

            const response = await axios.post('http://localhost:11434/api/chat', payload);
            let rawOutput = response.data.message.content;

            const thinkMatch = rawOutput.match(/<think>([\s\S]*?)<\/think>/i);
            if (thinkMatch) {
                console.log(`\n\x1b[90m[Qwen is thinking...]\n${thinkMatch[1].trim()}\x1b[0m\n`);
                finalResponseText = rawOutput.replace(/<think>[\s\S]*?<\/think>/i, "").trim();
            } else {
                finalResponseText = rawOutput.trim();
            }
        }
        else {
            if (messages.length > 20) messages.splice(1, 2); 
            messages.push({ role: "user", content: userText });

            const response = await groq.chat.completions.create({
                model: config.GROQ_MODEL, messages: messages, tools: tools, tool_choice: "auto", max_completion_tokens: 150, temperature: 0.5
            });

            const responseMessage = response.choices[0].message;
            if (responseMessage.tool_calls && responseMessage.tool_calls.length > 0) {
                const toolCall = responseMessage.tool_calls[0]; 
                const functionName = toolCall.function.name;
                
                if (functionName === "analyze_screen") {
                    const screenData = await actionHandler.captureScreen();
                    if (!screenData.success) return screenData.message;

                    messages.push(responseMessage);
                    messages.push({ role: "tool", tool_call_id: toolCall.id, name: functionName, content: "Screenshot captured." });

                    const visionResponse = await groq.chat.completions.create({
                        model: "meta-llama/llama-4-scout-17b-16e-instruct",
                        messages: [
                            { role: "system", content: "You are Quince. Describe the screen concisely." },
                            { role: "user", content: [{ type: "text", text: `Analyze this screen: "${userText}"` }, { type: "image_url", image_url: { url: `data:image/jpeg;base64,${screenData.base64}` } }]}
                        ],
                        max_completion_tokens: 200
                    });

                    finalResponseText = visionResponse.choices[0].message.content;
                    messages.push({ role: "assistant", content: finalResponseText });
                } 
                else {
                    const args = JSON.parse(toolCall.function.arguments || "{}");
                    let actionResult;
                    
                    // --- UPDATED TO PASS DESKTOP NUMBER ---
                    if (functionName === "open_application") actionResult = await actionHandler.openApplication(args.app_name, args.desktop_number);
                    else if (functionName === "search_web") actionResult = await actionHandler.searchWeb(args.query);
                    else if (functionName === "lock_screen") actionResult = await actionHandler.lockScreen();

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

        if (mode === 'local') await addMemory("quince", finalResponseText);
        return finalResponseText;

    } catch (error) {
        console.error("[LLM Error]", error.message);
        return "My brain is currently disconnected.";
    }
}

module.exports = { transcribeAudio, processPrompt, synthesizeSpeech };