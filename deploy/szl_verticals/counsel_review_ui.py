"""Static, no-third-party PRISM review client; user text is never interpolated."""
import base64
import hashlib
import re

REVIEW_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRISM Counsel | Text integrity workbench</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#090f1b;color:#e8eef8}
*{box-sizing:border-box}body{margin:0}main{max-width:1000px;margin:auto;padding:clamp(16px,4vw,40px)}
a{color:#91e2ff}h1{font-size:clamp(1.7rem,5vw,2.7rem);line-height:1.15}p{line-height:1.6}
.eyebrow{color:#91e2ff;letter-spacing:.12em}section{margin-top:24px;padding:20px;border:1px solid #456178;border-radius:16px;background:linear-gradient(120deg,#0f1d30,#101624)}
label{display:block;font-weight:650;margin:18px 0 8px}textarea,select,button{font:inherit;max-width:100%;border:1px solid #6686a1;border-radius:8px}
textarea,select{width:100%;padding:12px;background:#0a1423;color:inherit}textarea{min-height:100px;resize:vertical}
button{min-height:44px;padding:10px 18px;margin:16px 8px 0 0;background:#b3eeff;color:#061421;font-weight:700;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}:focus-visible{outline:3px solid #f5ce77;outline-offset:3px}
.note{color:#c3d0e0;font-size:.95rem}.status{overflow-wrap:anywhere;font-weight:650}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:520px;overflow:auto;background:#08101c;padding:16px}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:12px;border-bottom:1px solid #456178;overflow-wrap:anywhere}
@media(forced-colors:active){section,textarea,button,pre{border:1px solid CanvasText;background:Canvas;color:CanvasText}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body><main>
<p class="eyebrow">PRISM COUNSEL / EVIDENCE WORKBENCH</p>
<h1>Check the passage.<br>Keep the legal judgment human.</h1>
<p>This tool checks a quotation against the exact text you submit and returns a reproducible digest. It does not retrieve case law, establish citation validity, evaluate legal reasoning, or determine deadlines.</p>
<p class="note"><strong>Evaluation surface, not a privileged production workspace.</strong> Use public or synthetic text. This client keeps input in page memory, uses no browser persistence, and sends it only when you press Review. Transport, access and retention outside this handler require separate production qualification.</p>
<section aria-labelledby="input-title"><h2 id="input-title">Source → passage → reported claim</h2>
<label for="document">Source text (maximum 64,000 UTF-8 bytes)</label><textarea id="document" maxlength="64000" spellcheck="false"></textarea>
<label for="statement">Claim to review</label><textarea id="statement" maxlength="2000"></textarea>
<label for="quote">Exact quotation (must occur once in the source text)</label><textarea id="quote" maxlength="4000" spellcheck="false"></textarea>
<label for="relationship">Your reported relationship — not a model finding</label>
<select id="relationship"><option value="SUPPORT">Supporting text</option><option value="ADVERSE">Adverse text</option><option value="CONTEXT">Context only</option></select>
<button id="review" type="button">Review text integrity</button><button id="sample" type="button">Load synthetic example</button><button id="clear" type="button">Clear</button>
<p id="status" class="status" role="status" aria-live="polite">No source has been submitted.</p></section>
<section aria-labelledby="result-title"><h2 id="result-title">Review receipt</h2>
<p class="note">An anchored claim is not a legally supported claim. Supporting/adverse relationships remain caller-reported. Duplicate content is not independent authority.</p>
<div class="table-wrap"><table><caption>Claim-level textual integrity</caption><thead><tr><th scope="col">Claim</th><th scope="col">Support anchors</th><th scope="col">Adverse anchors</th><th scope="col">Text state</th></tr></thead><tbody id="rows"></tbody></table></div>
<pre id="receipt" tabindex="0" aria-label="Machine-readable receipt">No receipt yet.</pre></section>
<script>
'use strict';
const el=id=>document.getElementById(id);
let active=null;
function wipeResults(){el('rows').replaceChildren();el('receipt').textContent='No receipt yet.';}
function render(result){
  wipeResults();
  for(const claim of result.claims){const row=document.createElement('tr');
    for(const value of [claim.claim_id,claim.supporting_text_anchors,claim.adverse_text_anchors,claim.textual_support_state]){
      const cell=document.createElement('td');cell.textContent=String(value);row.appendChild(cell);
    }el('rows').appendChild(row);
  }el('receipt').textContent=JSON.stringify(result,null,2);el('status').textContent=result.decision;
}
el('sample').addEventListener('click',()=>{
  if(active)return;
  el('document').value='SYNTHETIC EXAMPLE. Notice must be delivered in writing.';
  el('statement').value='The example contains a written-notice provision.';
  el('quote').value='Notice must be delivered in writing.';el('relationship').value='SUPPORT';
  wipeResults();el('status').textContent='Synthetic example loaded. Nothing submitted.';
});
el('clear').addEventListener('click',()=>{
  if(active)active.abort();active=null;el('review').disabled=false;
  for(const id of ['document','statement','quote'])el(id).value='';
  wipeResults();el('status').textContent='Page input cleared. No persistent deletion is claimed.';
});
el('review').addEventListener('click',async()=>{
  if(active)return;
  const controller=new AbortController();active=controller;el('review').disabled=true;wipeResults();
  let timer;
  try{
    const text=el('document').value,quote=el('quote').value,statement=el('statement').value;
    const bytes=new TextEncoder().encode(text);
    if(!text.trim()||!quote||!statement.trim()||bytes.length>64000)throw new Error('Provide bounded source text, claim, and quotation.');
    const position=text.indexOf(quote);
    if(position<0||text.indexOf(quote,position+1)>=0)throw new Error('The exact quotation must occur once. Use the API for explicit multi-passage offsets.');
    const hash=await crypto.subtle.digest('SHA-256',bytes);
    if(active!==controller)return;
    const sha=Array.from(new Uint8Array(hash),v=>v.toString(16).padStart(2,'0')).join('');
    const start=Array.from(text.slice(0,position)).length,end=start+Array.from(quote).length;
    const payload={documents:[{document_id:'source-1',text,expected_sha256:sha}],claims:[{
      claim_id:'claim-1',statement,anchors:[{document_id:'source-1',start,end,quote,relationship:el('relationship').value}]
    }]};
    el('status').textContent='Reviewing submitted text; no legal authority is being established.';
    timer=setTimeout(()=>controller.abort(),15000);
    const response=await fetch('/counsel/v1/claim-integrity',{method:'POST',credentials:'omit',redirect:'error',cache:'no-store',
      signal:controller.signal,headers:{'Content-Type':'application/json','X-SZL-Session':crypto.randomUUID()},body:JSON.stringify(payload)});
    if(!response.ok)throw new Error('Review unavailable (HTTP '+response.status+'). No success receipt was produced.');
    const result=await response.json();if(active!==controller)return;render(result);
  }catch(error){if(active===controller)el('status').textContent=error.name==='AbortError'?'Review cancelled or timed out. No completion is claimed.':error.message;}
  finally{clearTimeout(timer);if(active===controller){active=null;el('review').disabled=false;}}
});
</script></main></body></html>'''


def _inline_hash(tag: str) -> str:
    blocks = re.findall(rf"<{tag}>(.*?)</{tag}>", REVIEW_HTML, flags=re.DOTALL)
    if len(blocks) != 1:
        raise RuntimeError("review UI must have exactly one static inline block per type")
    value = hashlib.sha256(blocks[0].encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(value).decode("ascii")


REVIEW_CSP = (
    f"default-src 'none'; script-src '{_inline_hash('script')}'; "
    f"style-src '{_inline_hash('style')}'; connect-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'self' https://huggingface.co"
)
