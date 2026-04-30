const { exec, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const stringSimilarity = require('string-similarity');

let appIndex = {}; 
let appNames = [];

const fallbackAppMap = {
    "whatsapp": "whatsapp:",
    "settings": "ms-settings:",
    "chrome": "chrome",
    "notepad": "notepad",
    "calculator": "calc"
};

function buildAppIndex() {
    console.log("[Action Handler] Scanning PC for installed applications...");
    
    const startMenuPaths = [
        path.join(process.env.APPDATA, 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        path.join(process.env.ProgramData, 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    ];

    function scanDirectory(directory) {
        if (!fs.existsSync(directory)) return;
        
        const files = fs.readdirSync(directory);
        for (const file of files) {
            const fullPath = path.join(directory, file);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                scanDirectory(fullPath);
            } else if (fullPath.endsWith('.lnk') || fullPath.endsWith('.exe')) {
                const cleanName = path.basename(file, path.extname(file)).toLowerCase();
                appIndex[cleanName] = fullPath;
                appNames.push(cleanName);
            }
        }
    }

    startMenuPaths.forEach(scanDirectory);

    Object.keys(fallbackAppMap).forEach(key => {
        appIndex[key] = fallbackAppMap[key];
        appNames.push(key);
    });

    console.log(`[Action Handler] Index built with ${appNames.length} applications.`);
}

buildAppIndex();

// --- UPDATED: Added desktopNumber logic ---
async function openApplication(appName, desktopNumber = null) {
    return new Promise((resolve) => {
        const query = appName.toLowerCase().trim();
        const matches = stringSimilarity.findBestMatch(query, appNames);
        const bestMatch = matches.bestMatch;

        if (bestMatch.rating >= 0.6) {
            const commandTarget = appIndex[bestMatch.target];
            
            // If the LLM passed a desktop number, switch to it first
            if (desktopNumber) {
                const pythonExecutable = path.join(__dirname, '..', 'services', 'venv', 'Scripts', 'python.exe');
                const scriptPath = path.join(__dirname, '..', 'services', 'desktop_manager.py');
                
                console.log(`\x1b[90m[Action Handler] Switching to virtual desktop ${desktopNumber}...\x1b[0m`);
                try {
                    execSync(`"${pythonExecutable}" "${scriptPath}" ${desktopNumber}`);
                } catch(e) {
                    console.error("[Action Handler] Failed to switch desktop.");
                }
            }

            const command = `start "" "${commandTarget}"`;
            console.log(`\x1b[90m[Action Handler] Executing: ${command}\x1b[0m`);
            
            exec(command, (error) => {
                if (error) {
                    resolve({ success: false, message: `I encountered an error trying to open ${bestMatch.target}.` });
                } else {
                    let msg = `I have opened ${bestMatch.target}.`;
                    if (desktopNumber) msg = `I switched to desktop ${desktopNumber} and opened ${bestMatch.target}.`;
                    resolve({ success: true, message: msg });
                }
            });
        } else {
            resolve({ success: false, message: `I couldn't find an application closely matching ${appName}.` });
        }
    });
}

async function searchWeb(query) {
    return new Promise((resolve) => {
        const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
        exec(`start "" "${url}"`, (error) => {
            if (error) resolve({ success: false, message: `I couldn't complete the web search.` });
            else resolve({ success: true, message: `Here are the search results for ${query}.` });
        });
    });
}

async function lockScreen() {
    return new Promise((resolve) => {
        exec(`rundll32.exe user32.dll,LockWorkStation`, (error) => {
            if (error) resolve({ success: false, message: `I failed to lock the screen.` });
            else resolve({ success: true, message: `Your workstation is locked.` });
        });
    });
}

function getCurrentTime() {
    return { success: true, data: new Date().toLocaleString() };
}

async function captureScreen() {
    return new Promise((resolve, reject) => {
        const pythonExecutable = path.join(__dirname, '..', 'services', 'venv', 'Scripts', 'python.exe');
        const scriptPath = path.join(__dirname, '..', 'services', 'screen_grab.py');
        
        exec(`"${pythonExecutable}" "${scriptPath}"`, { maxBuffer: 1024 * 1024 * 10 }, (error, stdout, stderr) => {
            if (error || stdout.startsWith('ERROR:')) resolve({ success: false, message: "Failed to capture the screen." });
            else resolve({ success: true, base64: stdout.trim() });
        });
    });
}

module.exports = { openApplication, searchWeb, lockScreen, getCurrentTime, captureScreen };