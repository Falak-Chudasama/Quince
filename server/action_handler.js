const { exec } = require('child_process');
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
    Object.keys(fallbackAppMap).forEach(key => { appIndex[key] = fallbackAppMap[key]; appNames.push(key); });
    console.log(`[Action Handler] Index built with ${appNames.length} applications.`);
}
buildAppIndex();

// --- NEW HELPER: Desktop Matcher ---
async function switchDesktop(targetName) {
    return new Promise((resolve) => {
        if (!targetName) return resolve({ success: true, message: "" });
        
        const pythonExecutable = path.join(__dirname, '..', 'services', 'venv', 'Scripts', 'python.exe');
        const scriptPath = path.join(__dirname, '..', 'services', 'desktop_manager.py');
        
        console.log(`\x1b[90m[Action Handler] Matching desktop for: "${targetName}"...\x1b[0m`);
        exec(`"${pythonExecutable}" "${scriptPath}" "${targetName}"`, (error, stdout) => {
            try {
                const result = JSON.parse(stdout.trim());
                if (result.success) console.log(`\x1b[90m[Action Handler] ${result.message}\x1b[0m`);
                resolve(result);
            } catch (e) {
                resolve({ success: false, message: "Failed to parse desktop manager output." });
            }
        });
    });
}

async function openApplication(appName, desktopTarget = null) {
    return new Promise(async (resolve) => {
        const query = appName.toLowerCase().trim();
        const matches = stringSimilarity.findBestMatch(query, appNames);
        const bestMatch = matches.bestMatch;

        if (bestMatch.rating >= 0.6) {
            let desktopMsg = "";
            if (desktopTarget) {
                const desktopResult = await switchDesktop(desktopTarget);
                if (desktopResult.success) desktopMsg = ` on ${desktopResult.message.replace("Switched to ", "")}`;
            }

            const commandTarget = appIndex[bestMatch.target];
            const command = `start "" "${commandTarget}"`;
            console.log(`\x1b[90m[Action Handler] Executing: ${command}\x1b[0m`);
            
            exec(command, (error) => {
                if (error) resolve({ success: false, message: `I encountered an error trying to open ${bestMatch.target}.` });
                else resolve({ success: true, message: `I have opened ${bestMatch.target}${desktopMsg}.` });
            });
        } else {
            resolve({ success: false, message: `I couldn't find an application closely matching ${appName}.` });
        }
    });
}

async function searchWeb(query, desktopTarget = null) {
    return new Promise(async (resolve) => {
        let desktopMsg = "";
        if (desktopTarget) {
            const desktopResult = await switchDesktop(desktopTarget);
            if (desktopResult.success) desktopMsg = ` on ${desktopResult.message.replace("Switched to ", "")}`;
        }

        const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
        exec(`start "" "${url}"`, (error) => {
            if (error) resolve({ success: false, message: `I couldn't complete the web search.` });
            else resolve({ success: true, message: `Here are the search results for ${query}${desktopMsg}.` });
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
    return new Promise((resolve) => {
        const pythonExecutable = path.join(__dirname, '..', 'services', 'venv', 'Scripts', 'python.exe');
        const scriptPath = path.join(__dirname, '..', 'services', 'screen_grab.py');
        exec(`"${pythonExecutable}" "${scriptPath}"`, { maxBuffer: 1024 * 1024 * 10 }, (error, stdout) => {
            if (error || stdout.startsWith('ERROR:')) resolve({ success: false, message: "Failed to capture screen." });
            else resolve({ success: true, base64: stdout.trim() });
        });
    });
}

module.exports = { openApplication, searchWeb, lockScreen, getCurrentTime, captureScreen };