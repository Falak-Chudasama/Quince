const PythonBridge = require('./bridge');
const groqService = require('./groq_service');
const path = require('path');

console.log("==========================================");
console.log(" Quince Cloud-Accelerated Controller Initializing... ");
console.log("==========================================\n");

const bridge = new PythonBridge(async (message) => {
    if (message.type === 'audio_ready') {
        const inputAudioPath = message.data;
        
        const userPrompt = await groqService.transcribeAudio(inputAudioPath);
        if (!userPrompt) {
            console.log("[Quince] I couldn't hear that clearly.");
            return;
        }
        console.log(`[User] ${userPrompt}`);

        const responseText = await groqService.processPrompt(userPrompt);
        console.log(`[Quince] ${responseText}`);

        const outputAudioPath = path.resolve(__dirname, '..', 'services', 'temp_response.wav');
        const ttsSuccess = await groqService.synthesizeSpeech(responseText, outputAudioPath);
        
        if (ttsSuccess) {
            bridge.sendToPython('play_audio', outputAudioPath);
        }
    } 
    else if (message.type === 'status') {
        console.log(`[Python] ${message.data}`);
    } 
    else if (message.type === 'error') {
        console.error(`[Python Error] ${message.data}`);
    }
});

process.stdin.resume();