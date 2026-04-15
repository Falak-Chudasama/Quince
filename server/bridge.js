const { spawn } = require('child_process');
const path = require('path');

class PythonBridge {
    constructor(onMessageCallback) {
        this.onMessageCallback = onMessageCallback;
        const pythonScriptPath = path.join(__dirname, '..', 'services', 'main.py');
        const pythonExecutable = path.join(__dirname, '..', 'services', 'venv', 'Scripts', 'python.exe');

        this.pythonProcess = spawn(pythonExecutable, [pythonScriptPath]);
        this.pythonProcess.stdout.on('data', (data) => this.handleData(data));
        this.pythonProcess.stderr.on('data', (data) => console.error(`[Python Log] ${data.toString()}`));
    }

    handleData(data) {
        const lines = data.toString().split('\n');
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            try {
                const payload = JSON.parse(trimmed);
                this.onMessageCallback(payload);
            } catch (e) {
                console.log(`[Python Log] ${trimmed}`);
            }
        }
    }

    sendToPython(type, data) {
        const payload = JSON.stringify({ type, data });
        this.pythonProcess.stdin.write(payload + '\n');
    }
}

module.exports = PythonBridge;