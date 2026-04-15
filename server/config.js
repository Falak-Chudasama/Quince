require('dotenv').config();

if (!process.env.GROQ_API_KEY) {
    console.error("CRITICAL ERROR: GROQ_API_KEY is missing in .env file.");
    process.exit(1);
}

module.exports = {
    GROQ_API_KEY: process.env.GROQ_API_KEY,
    GROQ_MODEL: process.env.GROQ_MODEL || "llama3-70b-8192",
    SYSTEM_PROMPT: `You are Quince, a highly efficient, conversational Windows desktop assistant. 
Your goal is to help the user by answering questions or executing desktop actions. 
Keep conversational responses very brief, natural, and to the point. Do not use markdown or emojis, as your output will be read aloud by a Text-to-Speech engine.`
};