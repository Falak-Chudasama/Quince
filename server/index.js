const PythonBridge = require('./bridge');
const groqService = require('./groq_service');
const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');
const axios = require('axios');

// Define the absolute path to your Python virtual environment
const venvPython = path.join(__dirname, '..', 'services', 'venv', 'Scripts', 'python.exe');

// ==========================================
// QUINCE UI COLORS (Pear Logo Gradient)
// ==========================================
const C_PEAR = "\x1b[38;2;168;224;99m";   // Green
const C_GOLD = "\x1b[38;2;246;211;101m";   // Yellow
const C_FIRE = "\x1b[38;2;253;160;133m";   // Orange
const C_DIM = "\x1b[90m";
const C_RESET = "\x1b[0m";

console.clear();
console.log(`${C_PEAR}==========================================`);
console.log(`${C_GOLD} 🍐 QUINCE HYBRID INTELLIGENCE AGENT`);
console.log(`${C_FIRE}==========================================${C_RESET}\n`);

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: `${C_PEAR}[You]: ${C_RESET}`
});

let currentMode = "cloud";
let bridge;
let ragServer;

// Helper to safely print background events without breaking the typing prompt
function safeLog(msg) {
    process.stdout.clearLine(0);
    process.stdout.cursorTo(0);
    console.log(msg);
    rl.prompt(true); 
}

// 1. Ask for Mode & Boot the RAG Server
rl.question(`${C_GOLD}? Select Inference Mode (cloud/local) [cloud]: ${C_RESET}`, async (answer) => {
    currentMode = answer.trim().toLowerCase() || 'cloud';
    console.log(`\n${C_DIM}> Initializing ${currentMode.toUpperCase()} mode...${C_RESET}`);
    console.log(`${C_DIM}> Booting Local Memory Server (Loading PyTorch)...${C_RESET}`);
    
    // --- SPAWN PERSISTENT RAG SERVER ---
    ragServer = spawn(venvPython, [path.join(__dirname, '..', 'services', 'rag_server.py')]);
    
    ragServer.stderr.on('data', (data) => {
        if (data.toString().includes("Error") || data.toString().includes("Exception")) {
            console.log(`\x1b[31m[Memory Server Error] ${data.toString().trim()}${C_RESET}`);
        }
    });

    // Give FastAPI and PyTorch ~4 seconds to load the embedding model into RAM
    await new Promise(resolve => setTimeout(resolve, 4000)); 
    
    try {
        await axios.post('http://127.0.0.1:8001/flush');
        console.log(`${C_DIM}> Memory flushed. Session is clean.${C_RESET}\n`);
    } catch (e) {
        console.error(`${C_FIRE}> Warning: Memory Server didn't respond in time.${C_RESET}\n`);
    }
    
    startAgent();
});

// 2. Start the Agent (Dual Input: Text + Audio)
function startAgent() {
    bridge = new PythonBridge(async (message) => {
        if (message.type === 'audio_ready') {
            const inputAudioPath = message.data;
            safeLog(`${C_DIM}[Thinking...] Processing audio...${C_RESET}`);
            
            const userPrompt = await groqService.transcribeAudio(inputAudioPath);
            if (!userPrompt) {
                safeLog(`${C_FIRE}[Quince]${C_RESET} I couldn't hear that clearly.`);
                return;
            }
            
            safeLog(`${C_PEAR}[Audio]${C_RESET} ${userPrompt}`);
            await handlePrompt(userPrompt);
        } 
        else if (message.type === 'status') {
            safeLog(`${C_DIM}[System] ${message.data}${C_RESET}`);
        } 
        else if (message.type === 'error') {
            safeLog(`\x1b[31m[Error] ${message.data}${C_RESET}`);
        }
    });

    rl.prompt();

    rl.on('line', async (line) => {
        const text = line.trim();
        if (text.toLowerCase() === 'exit') {
            console.log(`${C_FIRE}Shutting down...${C_RESET}`);
            if (ragServer) ragServer.kill(); 
            process.exit(0);
        }
        if (text) {
            await handlePrompt(text);
        } else {
            rl.prompt();
        }
    });
}

// 3. Shared Brain Processing
async function handlePrompt(text) {
    safeLog(`${C_GOLD}[Thinking...] generating response...${C_RESET}`);
    
    const responseText = await groqService.processPrompt(text, currentMode);
    safeLog(`${C_FIRE}[Quince]:${C_RESET} ${responseText}\n`);

    const outputAudioPath = path.resolve(__dirname, '..', 'services', 'temp_response.wav');
    const ttsSuccess = await groqService.synthesizeSpeech(responseText, outputAudioPath);
    if (ttsSuccess) {
        bridge.sendToPython('play_audio', outputAudioPath);
    }
}