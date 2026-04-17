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

    Object.keys(fallbackAppMap).forEach(key => {
        appIndex[key] = fallbackAppMap[key];
        appNames.push(key);
    });

    console.log(`[Action Handler] Index built with ${appNames.length} applications.`);
}

buildAppIndex();

async function openApplication(appName) {
    return new Promise((resolve) => {
        const query = appName.toLowerCase().trim();
        
        const matches = stringSimilarity.findBestMatch(query, appNames);
        const bestMatch = matches.bestMatch;

        console.log(`[Action Handler] Best match for "${query}" is "${bestMatch.target}" (Rating: ${(bestMatch.rating * 100).toFixed(1)}%)`);

        if (bestMatch.rating >= 0.6) {
            const commandTarget = appIndex[bestMatch.target];
            const command = `start "" "${commandTarget}"`;
            
            console.log(`[Action Handler] Executing: ${command}`);
            
            exec(command, (error) => {
                if (error) {
                    console.error(`[Action Handler] Error:`, error.message);
                    resolve({ success: false, message: `I encountered an error trying to open ${bestMatch.target}.` });
                } else {
                    resolve({ success: true, message: `I have opened ${bestMatch.target}.` });
                }
            });
        } else {
            console.log(`[Action Handler] Match rating too low. Aborting.`);
            resolve({ success: false, message: `I couldn't find an application closely matching ${appName} on your PC.` });
        }
    });
}

async function searchWeb(query) {
    return new Promise((resolve) => {
        const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
        const command = `start "" "${url}"`;
        exec(command, (error) => {
            if (error) resolve({ success: false, message: `I couldn't complete the web search.` });
            else resolve({ success: true, message: `Here are the search results for ${query}.` });
        });
    });
}

async function lockScreen() {
    return new Promise((resolve) => {
        const command = `rundll32.exe user32.dll,LockWorkStation`;
        exec(command, (error) => {
            if (error) resolve({ success: false, message: `I failed to lock the screen.` });
            else resolve({ success: true, message: `Your workstation is locked.` });
        });
    });
}

function getCurrentTime() {
    const now = new Date();
    return { success: true, data: now.toLocaleString() };
}

module.exports = {
    openApplication,
    searchWeb,
    lockScreen,
    getCurrentTime
};