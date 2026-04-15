const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const stringSimilarity = require('string-similarity');

// Maps to store actual PC applications
let appIndex = {}; 
let appNames = [];

// Tricky apps that don't rely on start menu shortcuts
const fallbackAppMap = {
    "whatsapp": "whatsapp:",
    "settings": "ms-settings:",
    "chrome": "chrome",
    "notepad": "notepad",
    "calculator": "calc"
};

// Scan Windows Start Menu to find installed applications
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
                // Strip extension for the clean name
                const cleanName = path.basename(file, path.extname(file)).toLowerCase();
                appIndex[cleanName] = fullPath;
                appNames.push(cleanName);
            }
        }
    }

    startMenuPaths.forEach(scanDirectory);
    // Add our fallbacks into the index
    Object.keys(fallbackAppMap).forEach(key => {
        appIndex[key] = fallbackAppMap[key];
        appNames.push(key);
    });

    console.log(`[Action Handler] Index built with ${appNames.length} applications.`);
}

// Build the index immediately on startup
buildAppIndex();

async function openApplication(appName) {
    return new Promise((resolve) => {
        const query = appName.toLowerCase().trim();
        
        // Calculate relativeness against actual installed apps
        const matches = stringSimilarity.findBestMatch(query, appNames);
        const bestMatch = matches.bestMatch;

        console.log(`[Action Handler] Best match for "${query}" is "${bestMatch.target}" (Rating: ${(bestMatch.rating * 100).toFixed(1)}%)`);

        // Check if the match is 60% or higher
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