# app.py
# Single-file Flask website + Discord OAuth2 dashboard for VRTEX
# Save as app.py. Requires: pip install flask requests

import os, json, pathlib, requests
from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory, url_for
from functools import wraps

BASE = pathlib.Path(__file__).parent
SETTINGS_PATH = BASE / "server_settings.json"
MEMBERS_PATH = BASE / "members.json"

# Ensure persistence files exist
if not SETTINGS_PATH.exists():
    SETTINGS_PATH.write_text(json.dumps({}, indent=2))
if not MEMBERS_PATH.exists():
    MEMBERS_PATH.write_text(json.dumps({"plus_members": []}, indent=2))

def read_json(p):
    return json.loads(pathlib.Path(p).read_text())

def write_json(p, data):
    pathlib.Path(p).write_text(json.dumps(data, indent=2))

# Config from environment
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "")  # e.g. https://yourdomain.com/dashboard/callback
FLASK_SECRET = os.getenv("FLASK_SECRET", "change_this_secret")
API_BASE = "https://discord.com/api"
MANAGE_GUILD = 1 << 5

app = Flask(__name__, static_folder="static")
app.secret_key = FLASK_SECRET

# ------------------ Full HTML template (site + dashboard) ------------------
# Logo: put logo image at ./static/logo.png to show it (the <img> is included near header)
TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VRTEX TEAM — Bots & Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Antonio:wght@400;700&family=Exo+2:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#070708;--accent-cyan:#00F0FF;--accent-violet:#8A4CFF;--muted:#9AA3AD;--text:#EEF2F5}
*{box-sizing:border-box}body{margin:0;font-family:'Exo 2',system-ui,Arial;background:radial-gradient(600px 400px at 8% 8%, rgba(138,76,255,0.06),transparent),radial-gradient(500px 300px at 92% 92%, rgba(0,240,255,0.03),transparent),var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}
.container{max-width:1200px;margin:28px auto;padding:18px}
/* header */
.header{display:flex;justify-content:space-between;align-items:center;padding:14px;border-radius:12px;background:linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0.01));border:1px solid rgba(255,255,255,0.02);position:fixed;left:0;right:0;top:0;z-index:50}
.brand{display:flex;align-items:center;gap:14px}
.logo-box{width:68px;height:68px;border-radius:12px;background:linear-gradient(135deg,var(--accent-violet),var(--accent-cyan));display:flex;align-items:center;justify-content:center;overflow:hidden}
.logo-box img{width:100%;height:100%;object-fit:contain}
/* PLACE LOGO: put file at ./static/logo.png to display it above */
.brand h1{font-family:'Antonio';margin:0;font-size:20px}
.nav{display:flex;gap:12px;align-items:center}
.nav a{padding:8px 12px;border-radius:10px;color:var(--muted);text-decoration:none;font-weight:600}
.nav a:hover{color:var(--text);box-shadow:0 8px 40px rgba(138,76,255,0.06)}
.cta{display:flex;gap:10px}
.btn{padding:10px 16px;border-radius:12px;font-weight:700;border:1px solid rgba(255,255,255,0.04);cursor:pointer;background:transparent}
.btn.primary{background:linear-gradient(90deg,var(--accent-cyan),var(--accent-violet));color:#071018;box-shadow:0 10px 40px rgba(0,240,255,0.08)}
/* hero */
.hero{display:grid;grid-template-columns:1fr 420px;gap:28px;margin-top:96px;align-items:center}
.hero-card{padding:32px;border-radius:16px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border:1px solid rgba(255,255,255,0.02);backdrop-filter:blur(6px)}
.hero h2{font-family:'Antonio';margin:0;font-size:44px}
.hero p{color:var(--muted);margin-top:12px;line-height:1.6}
.hero-actions{display:flex;gap:12px;margin-top:18px}
.visual-card{border-radius:16px;padding:20px;background:linear-gradient(135deg, rgba(138,76,255,0.06), rgba(0,240,255,0.04));display:flex;flex-direction:column;align-items:center;justify-content:center}
/* hex visual */
.hex-wrap{width:260px;height:260px;display:flex;align-items:center;justify-content:center;position:relative}
.hex{width:220px;height:220px;background:linear-gradient(135deg,#071018, rgba(0,0,0,0.15));clip-path:polygon(25% 6%,75% 6%,100% 50%,75% 94%,25% 94%,0% 50%);display:flex;align-items:center;justify-content:center;border-radius:12px;box-shadow:0 20px 80px rgba(138,76,255,0.06)}
.hex h3{font-family:'Antonio';margin:0;color:var(--text)}
.hex-glow{position:absolute;filter:blur(30px);opacity:0.8;width:420px;height:420px;border-radius:10px; background: conic-gradient(from 120deg, rgba(0,240,255,0.12), rgba(138,76,255,0.12));z-index:-1}
/* bots grid */
.section{margin-top:28px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.card{padding:18px;border-radius:14px;background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);border:1px solid rgba(255,255,255,0.02);transition:transform .25s ease,box-shadow .25s ease}
.card:hover{transform:translateY(-8px);box-shadow:0 30px 60px rgba(0,0,0,0.6)}
.title{font-family:'Antonio';margin:8px 0}
.muted{color:var(--muted)}
/* commands page */
.container-page{max-width:1100px;margin:120px auto;padding:18px}
/* dashboard area */
.dashboard-wrap{display:flex;gap:18px;margin-top:18px}
.left{flex:1}
.right{width:420px}
.guild-card{padding:12px;border-radius:10px;background:linear-gradient(90deg, rgba(255,255,255,0.01),transparent);display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}
.form-row{display:flex;flex-direction:column;margin-top:8px}
.form-row input,.form-row select{padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.03);background:transparent;color:var(--text)}
.note{font-size:13px;color:var(--muted);margin-top:10px}
/* compare table */
.table{margin:20px auto;border-collapse:collapse;width:90%;max-width:900px}
.table th,.table td{border:1px solid rgba(255,255,255,0.04);padding:12px;background:linear-gradient(180deg, rgba(255,255,255,0.01),transparent)}
.table th{background:linear-gradient(90deg, rgba(0,240,255,0.06), rgba(138,76,255,0.04));}
/* footer */
footer{margin-top:36px;text-align:center;color:var(--muted);padding:20px}
@media (max-width:1024px){.hero{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)} .right{width:100%}}
@media (max-width:720px){.grid{grid-template-columns:1fr}.container{padding:12px}}
</style>
</head>
<body>
<div class="container">
  <header class="header">
    <div class="brand">
      <div class="logo-box">
        <!-- PLACE LOGO: put ./static/logo.png to show it -->
        <img src="/static/logo.png" alt="VRTEX logo" onerror="this.style.display='none'">
      </div>
      <div>
        <h1>VRTEX TEAM</h1>
        <div class="muted" style="font-size:12px">Powering the next generation of Discord automation</div>
      </div>
    </div>

    <nav class="nav">
      <a href="#home" onclick="navigate('home')">Home</a>
      <a href="#ourbots" onclick="navigate('ourbots')">Our Bots</a>
      <a href="#premium" onclick="navigate('premium')">Premium</a>
      <a href="#about" onclick="navigate('about')">About</a>
      <a href="#contact" onclick="navigate('contact')">Contact</a>
      <a href="#dashboard" onclick="navigate('dashboard')">Dashboard</a>
    </nav>

    <div class="cta">
      <a class="btn ghost" href="https://discord.com/invite/PqNk8qWMK6" target="_blank">Join Discord</a>
      <a class="btn primary" href="https://www.youtube.com/channel/UCYhCGwWLY76QofDl_r6Bljg" target="_blank">YouTube</a>
    </div>
  </header>

  <main>
    <section id="home" class="hero">
      <div class="hero-card">
        <h2>VRTEX TEAM</h2>
        <p>We create futuristic, secure and fun Discord bots — economy, security, moderation and games. No gambling. VRTEX+ premium unlocks advanced customization.</p>
        <div class="hero-actions">
          <a class="btn primary" href="https://discord.com/invite/PqNk8qWMK6" target="_blank">Join Our Server</a>
          <button class="btn" onclick="navigate('ourbots')">Explore Bots</button>
        </div>
        <div style="display:flex;gap:12px;margin-top:18px">
          <div style="flex:1" class="card"><strong>Community</strong><div class="muted" style="margin-top:8px">Active support channel, roadmap, and early access for contributors and VRTEX+ members.</div></div>
          <div style="width:240px" class="card"><strong>Team Media</strong><div class="muted" style="margin-top:8px">YouTube tutorials and feature previews.</div></div>
        </div>
      </div>

      <div class="visual-card">
        <div class="hex-glow"></div>
        <div class="hex-wrap"><div class="hex"><h3>VRTEX</h3></div></div>
        <div class="muted" style="margin-top:12px">Fast • Secure • Scalable</div>
      </div>
    </section>

    <section id="ourbots" class="section" style="display:none">
      <h2 style="font-family:Antonio">Our Bots</h2>
      <div class="grid">
        <div class="card">
          <div style="display:flex;gap:12px;align-items:center">
            <div style="width:64px;height:64px;border-radius:12px;background:linear-gradient(90deg,var(--accent-cyan),var(--accent-violet));display:flex;align-items:center;justify-content:center;color:#071018;font-weight:800">E</div>
            <div style="flex:1">
              <div class="title">VRTEX ECONOMY</div>
              <div class="muted">Advanced non-gambling economy with jobs, businesses, and VRTEX+ perks.</div>
            </div>
          </div>
          <div style="margin-top:12px;display:flex;gap:8px">
            <a class="btn" href="https://discord.com/oauth2/authorize?client_id=1426165017715277824" target="_blank">Invite</a>
            <button class="btn" onclick="navigate('commands')">Commands</button>
            <button class="btn" onclick="openModal('economy')">Learn</button>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;gap:12px;align-items:center">
            <div style="width:64px;height:64px;border-radius:12px;background:linear-gradient(90deg,#7D3CFF,#4BE1FF);display:flex;align-items:center;justify-content:center;color:#071018;font-weight:800">S</div>
            <div style="flex:1"><div class="title">VRTEX SECURITY</div><div class="muted">In production — coming soon.</div></div>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;gap:12px;align-items:center">
            <div style="width:64px;height:64px;border-radius:12px;background:linear-gradient(90deg,#4BE1FF,#7D3CFF);display:flex;align-items:center;justify-content:center;color:#071018;font-weight:800">M</div>
            <div style="flex:1"><div class="title">VRTEX MODERATION</div><div class="muted">In production — coming soon.</div></div>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;gap:12px;align-items:center">
            <div style="width:64px;height:64px;border-radius:12px;background:linear-gradient(90deg,#00FFFF,#7D3CFF);display:flex;align-items:center;justify-content:center;color:#071018;font-weight:800">G</div>
            <div style="flex:1"><div class="title">VRTEX GAMES</div><div class="muted">In production — coming soon.</div></div>
          </div>
        </div>
      </div>
    </section>

    <section id="commands" class="section" style="display:none">
      <h2 style="font-family:Antonio">VRTEX ECONOMY — Commands</h2>
      <div style="padding:12px;">
        <h3>Economy</h3>
        <p class="muted">vebalance • vedeposit [amount] • vewithdraw [amount] • vetransfer [@user] [amount] • veleaderboard • veprofile [@user]</p>
        <h3>Work & Jobs</h3>
        <p class="muted">vework • veapplyjob [job] • vequitjob • vejobs • vepromote</p>
        <h3>Business</h3>
        <p class="muted">vebusiness buy [name] • vebusiness upgrade [name] • vebusiness claim • vebusiness info [name]</p>
        <h3>Market & Items</h3>
        <p class="muted">veinventory • vebuy [item] • vesell [item] • vetrade [@user] [item/amount] • vemarket post</p>
        <h3>Games</h3>
        <p class="muted">vecardclash • vetrivia • vememorymatch</p>
        <h3>Settings</h3>
        <p class="muted">vesettings currency [name] • vesettings tax [rate%] • vesettings toggle [command] • vesettings prefix [new prefix] (VRTEX+ only)</p>
      </div>
    </section>

    <section id="premium" class="section" style="display:none">
      <h2 style="font-family:Antonio">VRTEX+ Premium</h2>
      <p class="muted">Unlock exclusive customization and multipliers.</p>
      <div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap;justify-content:center">
        <div style="background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);padding:18px;border-radius:12px;width:320px">
          <h3>$2 / month</h3>
          <p class="muted">Monthly subscription — advanced server edits, premium income multipliers, exclusive crates.</p>
          <button class="btn primary" onclick="showCompare('monthly')">Get Monthly</button>
        </div>
        <div style="background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);padding:18px;border-radius:12px;width:320px">
          <h3>$22 / year</h3>
          <p class="muted">Yearly — best value. All monthly perks plus long-term perks.</p>
          <button class="btn primary" onclick="showCompare('yearly')">Get Yearly</button>
        </div>
      </div>

      <div id="compareBox" style="margin-top:24px;display:none">
        <h3 style="text-align:center">VRTEX+ vs Normal</h3>
        <table class="table">
          <tr><th>Feature</th><th>Normal</th><th>VRTEX+</th></tr>
          <tr><td>Daily Reward</td><td>3000</td><td>4000</td></tr>
          <tr><td>Vote Reward</td><td>2000</td><td>3000</td></tr>
          <tr><td>Cooldown Reduction</td><td>None</td><td>-20%</td></tr>
          <tr><td>Business Tiers</td><td>1-2</td><td>3-5</td></tr>
          <tr><td>Server Prefix Change</td><td>❌</td><td>✅</td></tr>
          <tr><td>Exclusive Crates</td><td>❌</td><td>✅</td></tr>
        </table>
        <div style="text-align:center;margin-top:12px"><a id="proceedBtn" href="#" class="btn primary">Proceed to Payment</a></div>
      </div>
    </section>

    <section id="about" class="section" style="display:none">
      <h2 style="font-family:Antonio">About VRTEX</h2>
      <p class="muted">We’re a passionate development team creating the VRTEX series of Discord bots — built for reliability and user experience.</p>
    </section>

    <section id="contact" class="section" style="display:none">
      <h2 style="font-family:Antonio">Contact Us</h2>
      <p class="muted">Join our Discord or email the team.</p>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:12px">
        <a class="btn" href="https://discord.com/invite/PqNk8qWMK6" target="_blank">Join Discord</a>
        <a class="btn" href="mailto:thevrtexteam@gmail.com">Email Us</a>
      </div>
    </section>

    <!-- DASHBOARD -->
    <section id="dashboard" class="section" style="display:none">
      <h2 style="font-family:Antonio">Server Dashboard</h2>
      <p class="muted">Login with Discord to manage your server settings (you must have Manage Server permission).</p>

      <div id="authArea" style="margin-top:12px"></div>

      <div class="dashboard-wrap">
        <div class="left">
          <div class="card">
            <h3>Your Manageable Servers</h3>
            <div id="guildList" class="muted" style="margin-top:12px">Please login to see servers.</div>
          </div>

          <div class="card" style="margin-top:12px">
            <h3>Help</h3>
            <div class="muted">Only server managers with Manage Server permission can edit settings. Premium fields require VRTEX+ (team will add you to members.json after purchase).</div>
          </div>
        </div>

        <div class="right">
          <div class="card" id="editor" style="display:none">
            <h3 id="editorTitle">Server Settings</h3>
            <div class="note">Basic fields editable by any manager. Premium fields require VRTEX+.</div>
            <div style="margin-top:10px">
              <label>Currency</label><div><input id="f_currency" /></div>
              <label>Tax %</label><div><input id="f_tax" type="number" /></div>
              <label>Prefix</label><div><input id="f_prefix" /></div>

              <hr style="margin:12px 0;border:none;border-top:1px solid rgba(255,255,255,0.03)">

              <label>Daily Amount (premium)</label><div><input id="f_daily" type="number" /></div>
              <label>Drop Amount (premium)</label><div><input id="f_drop" type="number" /></div>
              <label>Work Multiplier (premium)</label><div><input id="f_workmult" step="0.1" type="number" /></div>
              <label>Drop Cooldown (seconds) (premium)</label><div><input id="f_dropcd" type="number" /></div>

              <label style="margin-top:8px">Enable Commands (toggle names, comma separated to disable)</label>
              <div><input id="f_disabled_commands" placeholder="e.g. vecardclash, vetrivia" /></div>

              <div style="margin-top:12px;display:flex;gap:8px">
                <button class="btn primary" id="saveBtn">Save Settings</button>
                <button class="btn" id="closeEditor">Close</button>
              </div>
              <div id="editorMsg" class="note"></div>
            </div>
          </div>
        </div>
      </div>
    </section>

  </main>

  <footer>
    Made with ❤️ by VRTEX TEAM • <a href="https://discord.com/invite/PqNk8qWMK6" style="color:var(--accent-cyan)">Discord</a> • <a href="https://www.youtube.com/channel/UCYhCGwWLY76QofDl_r6Bljg" style="color:var(--accent-violet)">YouTube</a>
  </footer>
</div>

<!-- modal -->
<div id="modal" style="position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,0.7);z-index:80">
  <div style="max-width:900px;width:100%;padding:18px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:12px;position:relative">
    <button onclick="closeModal()" style="position:absolute;right:12px;top:12px;background:transparent;border:none;color:var(--muted);font-size:18px">✕</button>
    <div id="modalContent"></div>
  </div>
</div>

<script>
// SPA navigation
function hideAll(){['home','ourbots','commands','premium','about','contact','dashboard'].forEach(id=>document.getElementById(id).style.display='none')}
function navigate(p){hideAll();document.getElementById(p).style.display='block'; if(p==='dashboard') initDashboard(); window.scrollTo({top:0,behavior:'smooth'})}
navigate('home')

// modal functions
function openModal(key){
  const BOT_INFO = {
    economy:{title:'VRTEX ECONOMY',desc:'Jobs, businesses, marketplaces, VRTEX+ premium features.',invite:'https://discord.com/oauth2/authorize?client_id=1426165017715277824'},
    security:{title:'VRTEX SECURITY',desc:'In production — coming soon.'},
    moderation:{title:'VRTEX MODERATION',desc:'In production — coming soon.'},
    games:{title:'VRTEX GAMES',desc:'In production — coming soon.'}
  }
  const d = BOT_INFO[key]||{title:key,desc:'Coming soon'}
  document.getElementById('modalContent').innerHTML = `<h2 style="font-family:Antonio">${d.title}</h2><p class="muted">${d.desc}</p>${d.invite?`<a class="btn primary" href="${d.invite}" target="_blank">Invite</a>`:''}`
  document.getElementById('modal').style.display='flex'
}
function closeModal(){document.getElementById('modal').style.display='none'}

// ------ Dashboard client side ------
async function api(path, opts){
  const r = await fetch(path, opts);
  if(!r.ok) return Promise.reject(await r.json().catch(()=>({error:'bad'})));
  return r.json();
}

let selectedGuild = null;
async function initDashboard(){
  document.getElementById('authArea').innerHTML = `<a class="btn" href="/dashboard/login">Login with Discord</a>`;
  try{
    const user = await api('/dashboard/api/user');
    if(user && user.id){
      document.getElementById('authArea').innerHTML = `<div class="muted">Logged in as ${user.username}#${user.discriminator}</div> <a class="btn" href="/dashboard/logout">Logout</a>`;
      const guilds = await api('/dashboard/api/guilds');
      const gl = document.getElementById('guildList'); gl.innerHTML = '';
      if(!guilds || guilds.length===0){ gl.innerHTML = '<div class="muted">No manageable guilds found.</div>'; return; }
      guilds.forEach(g=>{
        const el = document.createElement('div'); el.className='guild-card';
        el.innerHTML = `<div><strong>${g.name}</strong><div class="muted" style="font-size:12px">${g.id}</div></div><div><button class="btn" onclick="openEditor('${g.id}','${escape(g.name)}')">Configure</button></div>`;
        gl.appendChild(el);
      });
    }
  }catch(e){
    // not logged in
  }
}

async function openEditor(guildId,gnameEsc){
  selectedGuild = guildId;
  document.getElementById('editor').style.display='block';
  document.getElementById('editorTitle').innerText = decodeURIComponent(gnameEsc) + ' — Settings';
  document.getElementById('editorMsg').innerText = '';
  try{
    const s = await api(`/dashboard/api/get_settings/${guildId}`);
    document.getElementById('f_currency').value = s.currency || '💰';
    document.getElementById('f_tax').value = s.tax || 5;
    document.getElementById('f_prefix').value = s.prefix || 've';
    document.getElementById('f_daily').value = s.daily_amount || 3000;
    document.getElementById('f_drop').value = s.drop_amount || 1000;
    document.getElementById('f_workmult').value = s.work_multiplier || 1.0;
    document.getElementById('f_dropcd').value = (s.cooldowns && s.cooldowns.drop_seconds) || 3600;
    document.getElementById('f_disabled_commands').value = (s.disabled_commands||[]).join(', ')

    const plus = await api('/dashboard/api/is_plus');
    if(!plus.is_plus){
      ['f_daily','f_drop','f_workmult','f_dropcd'].forEach(id=>{document.getElementById(id).disabled=true; document.getElementById(id).style.opacity=0.6})
      document.getElementById('editorMsg').innerText = 'Upgrade to VRTEX+ to edit premium options.';
    } else {
      ['f_daily','f_drop','f_workmult','f_dropcd'].forEach(id=>{document.getElementById(id).disabled=false; document.getElementById(id).style.opacity=1})
      document.getElementById('editorMsg').innerText = '';
    }
  }catch(err){
    document.getElementById('editorMsg').innerText='Failed to load settings.'
  }
}

document.getElementById('saveBtn').addEventListener('click', async ()=>{
  if(!selectedGuild){ document.getElementById('editorMsg').innerText='Select a server first.'; return; }
  const payload = {
    currency: document.getElementById('f_currency').value,
    tax: Number(document.getElementById('f_tax').value),
    prefix: document.getElementById('f_prefix').value,
    daily_amount: Number(document.getElementById('f_daily').value),
    drop_amount: Number(document.getElementById('f_drop').value),
    work_multiplier: Number(document.getElementById('f_workmult').value),
    cooldowns: { drop_seconds: Number(document.getElementById('f_dropcd').value) },
    disabled_commands: document.getElementById('f_disabled_commands').value.split(',').map(s=>s.trim()).filter(Boolean)
  };
  try{
    const res = await fetch(`/dashboard/api/update_settings/${selectedGuild}`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    const json = await res.json();
    if(!res.ok) throw json;
    document.getElementById('editorMsg').innerText = 'Saved successfully.';
  }catch(err){
    const m = err && err.message ? err.message : JSON.stringify(err);
    document.getElementById('editorMsg').innerText = 'Error: ' + (m || 'Could not save');
  }
});

document.getElementById('closeEditor').addEventListener('click', ()=>{ selectedGuild=null; document.getElementById('editor').style.display='none' });

function showCompare(plan){
  document.getElementById('compareBox').style.display='block';
  document.getElementById('proceedBtn').href = '#'; // you'll replace this with payment link later
  window.location.hash = 'premium';
}

// initialize on load
</script>
</body>
</html>
"""

# ------------------ Flask routes: site and OAuth endpoints ------------------

@app.route("/")
def index():
    return render_template_string(TEMPLATE)

# Discord OAuth endpoints for dashboard
@app.route("/dashboard/login")
def dash_login():
    if not DISCORD_CLIENT_ID or not REDIRECT_URI:
        return "OAuth not configured. Set DISCORD_CLIENT_ID and REDIRECT_URI env vars.", 500
    scopes = "identify%20guilds"
    return redirect(f"{API_BASE}/oauth2/authorize?response_type=code&client_id={DISCORD_CLIENT_ID}&scope={scopes}&redirect_uri={REDIRECT_URI}")

@app.route("/dashboard/callback")
def dash_callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds"
    }
    headers = {"Content-Type":"application/x-www-form-urlencoded"}
    resp = requests.post(f"{API_BASE}/oauth2/token", data=data, headers=headers)
    if resp.status_code != 200:
        return f"Token error: {resp.text}", 400
    token = resp.json()
    session["access_token"] = token["access_token"]
    me = requests.get(f"{API_BASE}/users/@me", headers={"Authorization":f"Bearer {token['access_token']}"})
    if me.status_code == 200:
        session["user"] = me.json()
    return redirect("/#dashboard")

@app.route("/dashboard/logout")
def dash_logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard/api/user")
def api_user():
    return jsonify(session.get("user") or {})

@app.route("/dashboard/api/guilds")
def api_guilds():
    if "access_token" not in session:
        return jsonify([]), 401
    resp = requests.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization":f"Bearer {session['access_token']}"})
    if resp.status_code != 200:
        return jsonify({"error":"failed_fetch"}), 400
    guilds = resp.json()
    managed = [g for g in guilds if (int(g.get("permissions",0)) & MANAGE_GUILD) != 0]
    return jsonify(managed)

@app.route("/dashboard/api/get_settings/<guild_id>")
def api_get_settings(guild_id):
    if "access_token" not in session:
        return jsonify({"error":"not_logged_in"}), 401
    settings = read_json(SETTINGS_PATH)
    default = {
        "currency":"💰","tax":5,"prefix":"ve",
        "daily_amount":3000,"drop_amount":1000,"work_multiplier":1.0,
        "cooldowns":{"drop_seconds":3600},
        "disabled_commands": []
    }
    return jsonify(settings.get(guild_id, default))

@app.route("/dashboard/api/update_settings/<guild_id>", methods=["POST"])
def api_update_settings(guild_id):
    if "access_token" not in session:
        return jsonify({"error":"not_logged_in"}), 401
    # verify user manages guild
    resp = requests.get(f"{API_BASE}/users/@me/guilds", headers={"Authorization":f"Bearer {session['access_token']}"})
    if resp.status_code != 200:
        return jsonify({"error":"failed_fetch"}), 400
    guilds = resp.json()
    found = next((g for g in guilds if str(g.get("id"))==str(guild_id)), None)
    if not found or (int(found.get("permissions",0)) & MANAGE_GUILD) == 0:
        return jsonify({"error":"no_permission"}), 403

    user = session.get("user", {})
    uid = str(user.get("id"))
    payload = request.json or {}
    settings = read_json(SETTINGS_PATH)
    members = read_json(MEMBERS_PATH).get("plus_members", [])
    is_plus = uid in [str(x) for x in members]

    allowed_basic = ["currency","tax","prefix","disabled_commands"]
    allowed_premium = ["daily_amount","drop_amount","work_multiplier","cooldowns"]

    current = settings.get(guild_id, {})
    # apply basic
    for k in allowed_basic:
        if k in payload:
            current[k] = payload[k]
    # apply premium
    for k in allowed_premium:
        if k in payload:
            if not is_plus:
                return jsonify({"error":"premium_required","message":"VRTEX+ required to change this."}), 403
            current[k] = payload[k]
    settings[guild_id] = current
    write_json(SETTINGS_PATH, settings)
    return jsonify({"success":True,"settings":current})

@app.route("/dashboard/api/is_plus")
def api_is_plus():
    if "user" not in session:
        return jsonify({"is_plus":False})
    uid = str(session["user"].get("id"))
    members = read_json(MEMBERS_PATH).get("plus_members", [])
    return jsonify({"is_plus": uid in [str(x) for x in members]})

# serve static files (logo etc.)
@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory(str(BASE / "static"), p)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print("Starting VRTEX site + dashboard on port", port)
    app.run(host="0.0.0.0", port=port, debug=False)
