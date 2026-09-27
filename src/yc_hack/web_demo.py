"""Dependency-free browser view for the shared consensus timeline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .events import read_events


INDEX_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Consensus · Shared Trip Workspace</title>
<style>
:root{--bg:#08111f;--panel:#101d30;--line:#263c58;--text:#f4f7fb;--muted:#91a4bd;--cyan:#59d9ff;--green:#57e39a;--yellow:#ffd166;--red:#ff7188;--purple:#ad9cff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#173456 0,#08111f 44%);color:var(--text);font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}main{max-width:1280px;margin:auto;padding:30px 28px 60px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:28px}.brand{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--cyan);font-weight:800}.title{font-size:32px;margin:5px 0 0;letter-spacing:-.03em}.pill{padding:8px 13px;border:1px solid var(--line);border-radius:999px;color:var(--muted);background:#0d1929}.status{border:1px solid var(--line);background:linear-gradient(135deg,#122944,#0e1b2c);border-radius:18px;padding:22px 24px;margin-bottom:18px;display:flex;justify-content:space-between;align-items:center;gap:18px}.status h2{margin:0 0 3px;font-size:22px}.status p{margin:0;color:var(--muted)}.status strong{font-size:15px}.status .ok{color:var(--green)}.status .blocked{color:var(--red)}.status .live{color:var(--yellow)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}.stat,.panel{border:1px solid var(--line);background:rgba(16,29,48,.88);border-radius:15px;padding:16px}.stat small,.label{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}.stat b{display:block;font-size:23px;margin-top:5px}.layout{display:grid;grid-template-columns:1.25fr .75fr;gap:18px}.panel h3{margin:0 0 14px;font-size:16px}.timeline{display:flex;flex-direction:column;gap:13px}.round{border:1px solid var(--line);border-radius:13px;padding:16px;background:rgba(20,37,59,.8)}.round-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}.round-title{font-weight:800;color:var(--cyan)}.version{color:var(--muted);font-size:12px}.proposal{background:#0b1728;border:1px solid #274566;border-radius:10px;padding:12px;margin-bottom:12px}.proposal h4{margin:0 0 8px;font-size:13px;color:var(--purple)}.proposal-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.proposal-item{color:#dce7f5}.proposal-item b{color:var(--text)}.agents{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.agent{background:#0b1728;border-left:4px solid var(--yellow);border-radius:9px;padding:10px}.agent.approved{border-color:var(--green)}.agent.blocked{border-color:var(--red)}.agent.needs_revision{border-color:var(--yellow)}.agent-name{font-weight:800}.decision{float:right;font-size:11px;text-transform:uppercase;color:var(--muted)}.reason{clear:both;color:var(--muted);font-size:12px;margin-top:5px}.final{border-color:#267d5a;background:linear-gradient(145deg,#102f2a,#102136)}.final h3{color:var(--green)}.itinerary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.day{background:#0a1d2a;border:1px solid #205343;border-radius:9px;padding:10px}.day b{color:var(--green);font-size:12px}.day span{display:block;margin-top:5px;color:#d9e9e5;font-size:12px}.empty{color:var(--muted);padding:30px;text-align:center;border:1px dashed var(--line);border-radius:10px}.footer{margin-top:20px;color:var(--muted);font-size:12px}@media(max-width:900px){.layout{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}.agents,.itinerary{grid-template-columns:1fr 1fr}}@media(max-width:560px){main{padding:20px 14px}.top,.status{align-items:flex-start;flex-direction:column}.stats{grid-template-columns:1fr 1fr}.agents,.itinerary,.proposal-grid{grid-template-columns:1fr}}
</style><style>
.controls{display:flex;gap:8px;margin-top:14px}.btn{border:1px solid var(--line);border-radius:9px;background:#142942;color:var(--text);padding:10px 15px;font-weight:700;cursor:pointer}.btn.primary{background:#1a6680;border-color:var(--cyan)}.btn:disabled{opacity:.45;cursor:not-allowed}.conversation{display:flex;flex-direction:column;gap:12px;margin-bottom:22px}.bubble-row{display:flex;gap:10px;align-items:flex-start}.bubble-row.agent-row{flex-direction:row-reverse}.avatar{width:34px;height:34px;display:grid;place-items:center;border-radius:50%;background:#1d3c5c;color:var(--cyan);font-weight:800;font-size:11px;flex:0 0 auto}.agent-row .avatar{background:#2b2750;color:var(--purple)}.user-row .avatar{background:#594522;color:#ffe3a0}.system-row .avatar{background:#243b48;color:var(--cyan)}.bubble{max-width:86%;background:#142941;border:1px solid #294763;border-radius:4px 15px 15px 15px;padding:12px 15px}.agent-row .bubble{border-radius:15px 4px 15px 15px;background:#182642}.user-row .bubble{background:#302719;border-color:#8a6d2c}.system-row .bubble{background:#172b35}.bubble .speaker{font-weight:800;font-size:12px;color:var(--cyan);margin-bottom:3px}.agent-row .speaker{color:var(--purple)}.user-row .speaker{color:#ffe3a0}.bubble .meta{font-size:11px;color:var(--muted);margin-top:5px}.typing{color:var(--yellow);font-style:italic}.muted{color:var(--muted)}.source{margin-top:8px;padding-top:8px;border-top:1px solid #294763;color:#b6c9df;font-size:12px}.source b{color:var(--cyan)}.choice{display:inline-block;margin:5px 5px 0 0;padding:4px 7px;border:1px solid #8a6d2c;border-radius:999px;color:#ffe3a0;font-size:11px}.conflict{border-color:#8a6d2c;background:#302719}
</style><style>.layout{grid-template-columns:1fr .95fr}.itinerary{grid-template-columns:repeat(2,1fr);gap:12px}.final{padding:18px}.final p{color:#d9e9e5;line-height:1.65}.day{min-height:112px;padding:13px}.day span{line-height:1.55}</style></head><body data-demo="planning"><main>
<header class="top"><div><div class="brand">Together.AI</div><div class="title">Together.AI</div><div class="controls"><button class="btn primary" id="start" onclick="startDemo()">▶ Start live demo</button><button class="btn" id="reset" onclick="resetDemo()">↺ Reset</button></div><nav style="display:flex;gap:8px;margin-top:14px"><a href="/" style="color:var(--muted);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:6px 10px;font-size:12px">Planning demo</a><a href="/injection" style="color:var(--muted);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:6px 10px;font-size:12px">Injection demo</a></nav></div><div class="pill" id="session">Demo idle</div></header>
<section class="status"><div><h2 id="statusTitle">Connecting to shared state…</h2><p id="statusText">The coordinator is waiting for task events.</p></div><strong id="statusBadge" class="live">● LIVE</strong></section>
<section class="stats"><div class="stat"><small>Agents</small><b id="agentCount">—</b></div><div class="stat"><small>Rounds</small><b id="roundCount">—</b></div><div class="stat"><small>Proposal versions</small><b id="versionCount">—</b></div><div class="stat"><small>Events</small><b id="eventCount">—</b></div></section>
<div class="layout"><section class="panel"><h3>Live agent conversation</h3><div id="conversation" class="conversation"><div class="empty">Press Start live demo to begin.</div></div><h3>Shared negotiation timeline</h3><div id="timeline" class="timeline"><div class="empty">Waiting for task events…</div></div></section><aside class="panel"><h3>Current shared outcome</h3><div id="outcome"><div class="empty">No terminal outcome yet.</div></div><div class="footer">Private memories stay with their owning agent. This view contains only shared proposals and bounded decisions.</div></aside></div>
</main><script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty=v=>Array.isArray(v)?v.map(pretty).join(', '):v&&typeof v==='object'?[v.name||v.venue||v.place||v.restaurant||v.restaurant_name||'item',v.meal||v.type,v.description,v.note,v.dietary_fit||v.compatibility_note||v.compatibility].filter(Boolean).join(' — '):String(v??'—');
const demoMode=document.body.dataset.demo||'planning';
let shownEvents=0,playbackTimer=null;
function playbackEvents(events){if(shownEvents>events.length){shownEvents=0;if(playbackTimer){clearTimeout(playbackTimer);playbackTimer=null}}if(shownEvents<events.length&&!playbackTimer){playbackTimer=setTimeout(()=>{shownEvents+=1;playbackTimer=null;refresh()},2500)}window.playbackActive=shownEvents<events.length;let visible=events.slice(0,shownEvents);return demoMode==='injection'?visible.map(e=>e.type==='injection_run_completed'?{...e,type:'consensus_reached',demo_type:'safety'}:e):visible}
const nativeFetch=window.fetch.bind(window);window.fetch=async function(input,init){let url=String(input);if(url.includes('/api/')&&!url.includes('mode=')){url+=(url.includes('?')?'&':'?')+'mode='+encodeURIComponent(demoMode)}let response=await nativeFetch(url,init);if(url.includes('/api/events')){let events=await response.json();return new Response(JSON.stringify(playbackEvents(events)),{status:response.status,headers:{'Content-Type':'application/json'}})}if(url.includes('/api/status')&&window.playbackActive){let status=await response.json();status.running=true;return new Response(JSON.stringify(status),{status:response.status,headers:{'Content-Type':'application/json'}})}return response};
function proposalHtml(p,source){if(!p)return '';let ds=(p.destinations||[]).slice(0,5).map(d=>{let budget=typeof d.estimated_budget_usd_per_person==='number'?`$${esc(d.estimated_budget_usd_per_person)} / person`:'budget pending';let reason=d.reason?` — ${esc(d.reason)}`:'';return `<div><b>${esc(d.name||'Unnamed option')}</b> <span class="muted">(${budget})</span>${reason}</div>`}).join('');let days=(p.itinerary||[]).length;let window=(p.common_windows||[])[0];let food=(p.itinerary||[]).reduce((n,d)=>n+(Array.isArray(d.food)?d.food.length:0),0);return `<div class="proposal"><h4>PUBLIC PROPOSAL</h4><div class="proposal-grid"><div class="proposal-item"><b>Destination options:</b> ${ds||'—'}</div><div class="proposal-item"><b>Trip shape:</b> ${days||'—'} days${window?` · ${esc(window[0])} to ${esc(window[1])}`:''} · ${food} food stops</div></div>${source?`<div class="source"><b>Suggestion source:</b> ${esc(source)}</div>`:''}</div>`}
function agentHtml(d){let status=d.status||d.action||'unknown';return `<div class="agent ${esc(status)}"><span class="agent-name">${esc(d.agent_id)}</span><span class="decision">${esc(status)}</span><div class="reason">${esc(d.reason_code||'no reason code')}</div><div class="source">Reviewed coordinator proposal v${esc(d.proposal_version||'1')} · private constraints stayed with this agent</div></div>`}
function finalHtml(proposal,end){if(!end)return '<div class="empty">Consensus or blocked outcome will appear here.</div>';if(end.demo_type==='safety')return `<div class="final"><h3>Safety demo complete</h3><p>${esc(end.refused_count||0)} adversarial requests were refused or redacted.</p></div>`;if(end.type!=='consensus_reached')return `<div class="agent blocked"><b>BLOCKED — human decision required</b><div class="reason">${esc(end.reason_code||'resolution required')}</div><div class="source">The coordinator stopped and is waiting for an explicit user choice. No consent was inferred.</div></div>`;let p=proposal||{};let days=(p.itinerary||[]).map(d=>`<div class="day"><b>DAY ${esc(d.day)}</b><span><b>Activities:</b> ${esc(pretty(d.activities))}</span><span><b>Food:</b> ${esc(pretty(d.food))}</span></div>`).join('');return `<div class="final"><h3>Consensus reached</h3><p>All required agents approved proposal version ${esc(end.proposal_version||'')}.</p><div class="itinerary">${days||'<span>Itinerary unavailable</span>'}</div></div>`}
function messageHtml(e){let type=e.type,agent=type==='agent_contribution'||type==='agent_decision',user=type==='user_action_required'||type==='user_resolution_applied'||type==='user_approval_requested'||type==='user_approval_received',system=type==='safety_refusal'||type==='conflict_detected'||type==='soft_blocker_detected';let name=agent?(e.agent_id||'personal agent'):user?'User decision':system?(type==='safety_refusal'?'Safety guard':'Conflict resolver'):'Coordinator';let avatar=agent?String(name).slice(0,2).toUpperCase():user?'YOU':system?'!':'CO';let rowClass=agent?'agent-row':user?'user-row':system?'system-row':'';let text=type==='availability_computed'?`Common availability computed: ${(e.common_windows||[]).length} possible windows.`:type==='destinations_generated'?'I generated destination suggestions from the shared task context.':type==='proposal_published'?(e.stage==='proposal_landed'?`Proposal v${e.proposal_version||''} landed in shared state for all agents to review.`:`I published shared proposal v${e.proposal_version||''} for agent review.`):type==='safety_refusal'?(e.injected_query?`Injected query: ${e.injected_query} → ${e.shared_output||'refused or redacted.'}`:`${e.shared_output||'Request refused or redacted.'}`):type==='soft_blocker_detected'?`${e.summary||'A negotiable preference needs approval.'}`:type==='conflict_detected'?`${e.summary||'A constraint conflict needs resolution.'}`:type==='user_approval_requested'?(e.question||'May I apply this negotiable change?'):type==='user_approval_received'?`Explicit user response: ${e.decision||'unknown'}.`:type==='user_action_required'?(e.prompt||'Additional information or an explicit choice is required.'):type==='user_resolution_applied'?`Applied your explicit choice: ${e.destination||e.resolution_type||'resolution'}.`:type==='revision_required'?`I need to revise the proposal using the bounded agent feedback.`:type==='consensus_reached'?'All required agents approved the same proposal version.':type==='consensus_blocked'?`The workflow is blocked: ${e.reason_code||'resolution required'}.`:type==='budget_approval_required'?`The proposal needs explicit approval from: ${(e.affected_agents||[]).join(', ')}.`:agent?`${String(e.status||e.action||'response').replaceAll('_',' ')} · ${e.public_message||e.reason_code||'bounded response'}`:type.replaceAll('_',' ');let source=e.source_detail||e.source||'';let choices=(e.choices||[]).map(c=>`<span class="choice">${esc(c.replaceAll('_',' '))}</span>`).join('');return `<div class="bubble-row ${rowClass}"><div class="avatar">${esc(avatar)}</div><div class="bubble"><div class="speaker">${esc(name)}</div><div>${esc(text)}</div>${choices?`<div>${choices}</div>`:''}${source?`<div class="source"><b>Source:</b> ${esc(source)}</div>`:''}<div class="meta">${esc(type)}${e.round?' · round '+esc(e.round):''}</div></div></div>`}
async function startDemo(){let r=await fetch('/api/start',{method:'POST'});let data=await r.json();if(data.result==='missing_config'){statusText.textContent='Start the server with --config to run the live demo.'}}
async function resetDemo(){await fetch('/api/reset',{method:'POST'});shownEvents=0;if(playbackTimer){clearTimeout(playbackTimer);playbackTimer=null}conversation.innerHTML='<div class="empty">Demo idle. Press Start live demo.</div>';timeline.innerHTML='<div class="empty">Waiting for task events…</div>';outcome.innerHTML='<div class="empty">No terminal outcome yet.</div>'}
async function refresh(){try{let es=await (await fetch('/api/events?t='+Date.now())).json();let live=await (await fetch('/api/status?t='+Date.now())).json();let task=es.find(e=>e.type==='task_created'||e.type==='task_started');let pubs=es.filter(e=>e.type==='proposal_published'||e.type==='proposal_created');let rounds=[...new Set(es.filter(e=>e.round).map(e=>e.round))].sort((a,b)=>a-b);let end=[...es].reverse().find(e=>e.type==='consensus_reached'||e.type==='consensus_blocked'||e.type==='workflow_blocked');let agents=[...new Set(es.map(e=>e.agent_id).filter(Boolean))];session.textContent=task?`Session · ${task.task_id||'active'}`:(live.running?'Running live demo':'Idle');agentCount.textContent=agents.length||'—';roundCount.textContent=rounds.length||'—';versionCount.textContent=pubs.length||'—';eventCount.textContent=es.length;start.disabled=live.running;reset.disabled=live.running&&!es.length;if(end){let reached=end.type==='consensus_reached';statusTitle.textContent=reached?'Consensus reached':'Workflow blocked';statusText.textContent=reached?'The shared proposal passed every required agent approval.':`Resolution required · ${end.reason_code||'unknown reason'}`;statusBadge.textContent=reached?'● SUCCESS':'● BLOCKED';statusBadge.className=reached?'ok':'blocked'}else if(live.running){statusTitle.textContent='Agents are evaluating the proposal';statusText.textContent='Personal agents are entering the conversation as they pull work.';statusBadge.textContent='● LIVE';statusBadge.className='live'}else{statusTitle.textContent='Demo idle';statusText.textContent='Use Start live demo to launch the local Ollama workflow.';statusBadge.textContent='● IDLE';statusBadge.className='live'}conversation.innerHTML=es.filter(e=>['availability_computed','destinations_generated','proposal_published','safety_refusal','conflict_detected','budget_approval_required','user_action_required','user_resolution_applied','revision_required','agent_claimed','agent_contribution','consensus_reached','consensus_blocked','workflow_blocked'].includes(e.type)).map(messageHtml).join('')||'<div class="empty">Press Start live demo to begin.</div>';let html=rounds.map(r=>{let x=es.filter(e=>(e.round||1)===r);let p=x.find(e=>e.type==='proposal_published'||e.type==='proposal_created');let ds=x.filter(e=>e.type==='agent_decision'||e.type==='agent_contribution');return `<article class="round"><div class="round-head"><span class="round-title">ROUND ${esc(r)}</span><span class="version">${p?'Proposal v'+esc(p.proposal_version||r):'Agent responses'}</span></div>${proposalHtml(p&&p.proposal,p&&p.source_detail)}<div class="agents">${ds.length?ds.map(agentHtml).join(''):'<div class="empty">Waiting for agent responses…</div>'}</div></article>`}).join('');timeline.innerHTML=html||'<div class="empty">Waiting for task events…</div>';let lastProposal=pubs.length?pubs[pubs.length-1].proposal:null;outcome.innerHTML=finalHtml(lastProposal,end)}catch(e){statusTitle.textContent='Waiting for event stream';statusText.textContent='Start the server with --config to run the live demo.'}}refresh();setInterval(refresh,700);
</script></body></html>"""


def serve(events_path: str, host: str = "127.0.0.1", port: int = 8765, config_path: str | None = None) -> None:
    planning_path = Path(events_path)
    safety_path = planning_path.with_name(f"{planning_path.stem}-injection{planning_path.suffix}")
    config = Path(config_path) if config_path else None
    processes: dict[str, subprocess.Popen] = {}

    def mode_path(mode: str) -> Path:
        return safety_path if mode == "injection" else planning_path

    def write_planning_demo(path: Path) -> None:
        """Write a fast, deterministic trace for the browser recording.

        The browser demo must be repeatable even when a local Ollama model is
        slow or returns malformed itinerary JSON. The real workflow remains
        available through `yc_hack workflow`; this trace exercises the exact
        shared protocol and keeps the recording focused on coordination.
        """
        scenario = json.loads(config.read_text(encoding="utf-8")) if config else {}
        participants = list(scenario.get("participants", []))
        duration = int(scenario.get("task", {}).get("duration_days", 5))
        window = scenario.get("task", {}).get("planning_window", ["2026-10-01", "2026-10-31"])
        agents = participants[:3] or ["agent-1", "agent-2", "agent-3"]
        itinerary = [
            {"day": 1, "activities": ["Arrive and explore the historic center"], "food": [{"venue": "Green Market Kitchen", "meal": "vegetarian dinner", "compatibility_note": "Vegetarian option available; shellfish-free."}]},
            {"day": 2, "activities": ["Visit the main museum district", "Walk the riverfront"], "food": [{"venue": "Harbor Table", "meal": "local lunch", "compatibility_note": "Vegetarian option available; shellfish-free."}]},
            {"day": 3, "activities": ["Guided neighborhood tour", "Free afternoon"], "food": [{"venue": "Cedar & Grain", "meal": "vegetarian tasting menu", "compatibility_note": "Vegetarian option available; shellfish-free."}]},
            {"day": 4, "activities": ["Day trip to a nearby landmark", "Evening market"], "food": [{"venue": "Market Hall", "meal": "vegetarian market plates", "compatibility_note": "Vegetarian option available; shellfish-free."}]},
            {"day": 5, "activities": ["Final city walk", "Depart"], "food": [{"venue": "Sunrise Café", "meal": "vegetarian breakfast", "compatibility_note": "Vegetarian option available; shellfish-free."}]},
        ][:duration]
        destinations = [
            {"name": "Lisbon, Portugal", "estimated_budget_usd_per_person": 1450, "reason": "Strong shared availability and walkable activities."},
            {"name": "Prague, Czech Republic", "estimated_budget_usd_per_person": 1380, "reason": "Lower cost with museums, food, and flexible pacing."},
            {"name": "Vienna, Austria", "estimated_budget_usd_per_person": 1510, "reason": "Reliable transit and broad cultural options."},
        ]
        proposal = {"common_windows": [window], "destinations": destinations, "itinerary": itinerary, "budget_requests": [{"agent_id": agents[0], "preferred_limit": 1400, "absolute_maximum": 2000, "incremental_amount": 50}]}
        events = [
            {"type": "task_created", "task_id": "3 musketeers", "agent_count": len(agents), "source": "experiment_scenario"},
            {"type": "availability_computed", "common_windows": [window], "source_detail": "calendar intersection from shared availability windows"},
            {"type": "destinations_generated", "destinations": destinations, "source_detail": "coordinator recommendation from shared task requirements"},
            {"type": "soft_constraint_demo_seeded", "agent_id": agents[0], "preferred_limit": 1400, "absolute_maximum": 2000, "proposal_budget": 1450, "source": "profile budget preference"},
            {"type": "soft_blocker_detected", "blocker_type": "budget_preference", "affected_agents": [agents[0]], "summary": f"The proposal is $50 above {agents[0]}'s preferred budget, but remains within the stated $2000 absolute maximum.", "source": "coordinator constraint check"},
            {"type": "conflict_detected", "conflict_type": "soft_budget_preference", "reason_code": "preferred_budget_exceeded", "affected_agents": [agents[0]], "summary": "A negotiable preference needs the affected user's explicit approval.", "source": "coordinator outreach"},
            {"type": "user_approval_requested", "requested_from": agents[0], "question": "This proposal is $50 above your preferred $1400 budget but within your $2000 absolute maximum. May I approve it to preserve the group itinerary?", "source": "coordinator outreach"},
            {"type": "user_action_required", "requested_from": agents[0], "reason_code": "soft_blocker_approval", "prompt": "Please confirm whether to approve the small budget increase.", "choices": ["approve_budget_increase", "decline_budget_increase"], "source": "coordinator outreach"},
            {"type": "user_approval_received", "requested_from": agents[0], "decision": "approved", "source": "mock user approval API"},
            {"type": "user_resolution_applied", "agent_id": agents[0], "resolution_type": "budget_increase", "destination": "approved within absolute maximum", "source": "explicit user approval"},
            {"type": "proposal_published", "round": 1, "proposal_version": 1, "proposal": proposal, "stage": "proposal_landed", "source_detail": "coordinator landed the complete proposal in shared state"},
        ]
        for agent in agents:
            events.append({"type": "agent_claimed", "round": 1, "agent_id": agent, "proposal_version": 1})
            events.append({"type": "agent_contribution", "round": 1, "agent_id": agent, "proposal_version": 1, "status": "approved", "reason_code": "constraints_satisfied", "public_message": "I reviewed the landed proposal against my private constraints. I agree with the dates, pace, food compatibility, and approved budget tradeoff.", "source_detail": "personal agent review; private profile values were not shared"})
        events.append({"type": "consensus_reached", "round": 1, "proposal_version": 1, "status": "consensus_reached", "proposal": proposal, "source_detail": "all required personal agents approved the same public proposal"})
        path.write_text("".join(json.dumps({"session_id": "3 musketeers", "sequence": i + 1, **event}) + "\n" for i, event in enumerate(events)), encoding="utf-8")

    def start_workflow(mode: str) -> str:
        path = mode_path(mode)
        process = processes.get(mode)
        if process and process.poll() is None:
            return "already_running"
        if config is None:
            return "missing_config"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        env = os.environ.copy()
        if mode == "planning":
            write_planning_demo(path)
            return "started"
        if mode == "planning_ollama":
            env["YC_HACK_USER_APPROVAL_URL"] = f"http://{host}:{port}/api/user-approval"
            env["YC_HACK_DEMO_SOFT_BLOCKER"] = "1"
            command = [sys.executable, "-m", "yc_hack", "workflow", "--config", str(config), "--events", str(path)]
        else:
            command = [sys.executable, "-m", "yc_hack", "safety", "--config", str(config), "--events", str(path)]
        processes[mode] = subprocess.Popen(
            command,
            cwd=str(Path.cwd()), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return "started"

    def reset_workflow(mode: str) -> str:
        path = mode_path(mode)
        process = processes.get(mode)
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
        processes[mode] = None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return "reset"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            mode = parse_qs(parsed.query).get("mode", ["planning"])[0]
            if route == "/":
                body, content_type = INDEX_HTML.encode(), "text/html; charset=utf-8"
            elif route == "/injection":
                injection_html = INDEX_HTML.replace('data-demo="planning"', 'data-demo="injection"').replace(
                    "Consensus · Shared Trip Workspace", "Safety · Injection Boundary"
                ).replace("One trip. Three personal agents.", "Safety boundary · injection probes").replace(
                    "Start live demo", "Start injection demo"
                )
                body, content_type = injection_html.encode(), "text/html; charset=utf-8"
            elif route == "/api/events":
                try:
                    path = mode_path(mode)
                    body = json.dumps(read_events(path) if path.exists() else []).encode()
                except (OSError, ValueError):
                    body = b"[]"
                content_type = "application/json"
            elif route == "/api/status":
                process = processes.get(mode)
                running = bool(process and process.poll() is None)
                body = json.dumps({"running": running, "configured": config is not None}).encode()
                content_type = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            mode = parse_qs(parsed.query).get("mode", ["planning"])[0]
            if route == "/api/start":
                result = start_workflow(mode)
            elif route == "/api/reset":
                result = reset_workflow(mode)
            elif route == "/api/user-approval":
                # Demo adapter: stand in for a real user confirmation service.
                # The workflow still requires this explicit response before it
                # can continue past a negotiable blocker.
                result = {"decision": "yes", "source": "dummy_user_approval_api"}
            else:
                self.send_error(404)
                return
            body = json.dumps(result if isinstance(result, dict) else {"result": result}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            return

    print(f"demo_ui=http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
