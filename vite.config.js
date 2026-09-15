const { defineConfig } = require("vite");
const { resolve } = require("path");

module.exports = defineConfig({
    build: {
        rollupOptions: {
            input: {
                home: resolve(__dirname, "index.html"),
                login: resolve(__dirname, "login.html"),
                dashboard: resolve(__dirname, "dashboard.html"),
                chat: resolve(__dirname, "chat.html")
            }
        }
    }
});