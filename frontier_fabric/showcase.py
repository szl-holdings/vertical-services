from __future__ import annotations

from html import escape
from typing import Final

from .catalog import VERTICALS, get_vertical
from .types import VerticalSpec


_STAGE: Final[dict[str, str]] = {
    "a11oy": """
<section class="stage trajectory" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Decision trajectory</span><strong>bounded execution</strong></div>
  <div class="trajectory-line" aria-hidden="true"></div>
  <ol class="trajectory-steps" aria-label="Governed decision trajectory">
    <li data-node="signal"><b>01</b><span>Signal</span><small>observed</small></li>
    <li data-node="proposal"><b>02</b><span>Proposal</span><small>model · advisory</small></li>
    <li data-node="policy"><b>03</b><span>Policy</span><small>independent gate</small></li>
    <li data-node="bind"><b>04</b><span>Human bind</span><small>scope + identity</small></li>
    <li data-node="effect"><b>05</b><span>Effect</span><small>bounded adapter</small></li>
    <li data-node="receipt"><b>06</b><span>Receipt</span><small>verify + outcome</small></li>
  </ol>
  <div class="policy-chamber">
    <div><small>policy revision</small><strong>covenant/17</strong></div>
    <div><small>model authority</small><strong>none</strong></div>
    <div><small>human binding</small><strong>required</strong></div>
  </div>
</section>
""",
    "hatun": """
<section class="stage constellation" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Temporal council</span><strong>decision memory</strong></div>
  <div class="orbit orbit-one" aria-hidden="true"></div>
  <div class="orbit orbit-two" aria-hidden="true"></div>
  <button class="star star-intent is-active" data-node="intent" type="button"><b>Intent</b><small>why now</small></button>
  <button class="star star-evidence" data-node="evidence" type="button"><b>Evidence</b><small>what changed</small></button>
  <button class="star star-decision" data-node="decision" type="button"><b>Decision</b><small>who bound it</small></button>
  <button class="star star-commitment" data-node="commitment" type="button"><b>Commitment</b><small>owner + due</small></button>
  <button class="star star-outcome" data-node="outcome" type="button"><b>Outcome</b><small>what occurred</small></button>
  <div class="council-core"><span>HATUN</span><strong>confidence drift</strong><small>0.62 → 0.78</small></div>
</section>
""",
    "killinchu": """
<section class="stage radar" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Mission simulation</span><strong>public effectors disabled</strong></div>
  <div class="radar-field" aria-label="Synthetic track simulation">
    <div class="radar-ring ring-a" aria-hidden="true"></div>
    <div class="radar-ring ring-b" aria-hidden="true"></div>
    <div class="radar-ring ring-c" aria-hidden="true"></div>
    <div class="radar-sweep" aria-hidden="true"></div>
    <button class="track track-a is-active" data-node="synthetic-air-17" type="button"><b>A-17</b><small>synthetic · 0.71</small></button>
    <button class="track track-b" data-node="synthetic-sea-04" type="button"><b>M-04</b><small>historical planning</small></button>
    <button class="track track-c" data-node="unknown-09" type="button"><b>U-09</b><small>classification hold</small></button>
    <div class="rules-ring"><span>rules boundary</span><strong>SIMULATE ONLY</strong></div>
  </div>
  <div class="mission-clock"><span>T+ 00:03:18</span><span>seed 11</span><span>operator review required</span></div>
</section>
""",
    "sentra": """
<section class="stage nervous" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Exposure nervous system</span><strong>causal reachability</strong></div>
  <div class="nerve-map" aria-label="Synthetic attack-path graph">
    <div class="nerve edge-1" aria-hidden="true"></div><div class="nerve edge-2" aria-hidden="true"></div>
    <div class="nerve edge-3" aria-hidden="true"></div><div class="nerve edge-4" aria-hidden="true"></div>
    <button class="nerve-node node-kev is-active" data-node="kev" type="button"><small>CISA KEV</small><b>observed</b></button>
    <button class="nerve-node node-edge" data-node="edge" type="button"><small>edge service</small><b>reachable</b></button>
    <button class="nerve-node node-identity" data-node="identity" type="button"><small>identity path</small><b>conditional</b></button>
    <button class="nerve-node node-control" data-node="control" type="button"><small>control</small><b>partial</b></button>
    <button class="nerve-node node-impact" data-node="impact" type="button"><small>business service</small><b>at risk</b></button>
  </div>
  <div class="proof-stack"><span>exploit evidence</span><span>asset identity</span><span>control state</span><span>remediation proof</span></div>
</section>
""",
    "lyte": """
<section class="stage trace-river" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Causal trace river</span><strong>change → outcome</strong></div>
  <div class="river" aria-label="Synthetic service and business trace">
    <div class="river-labels"><span>deploy</span><span>service</span><span>journey</span><span>business</span></div>
    <button class="trace trace-deploy is-active" data-node="deploy" type="button"><b>rev 8c21</b><small>12:03:14</small></button>
    <button class="trace trace-api" data-node="api" type="button"><b>checkout.api</b><small>p95 +41%</small></button>
    <button class="trace trace-journey" data-node="journey" type="button"><b>payment</b><small>cohort west</small></button>
    <button class="trace trace-impact" data-node="impact" type="button"><b>conversion</b><small>−3.2% measured</small></button>
    <svg class="river-lines" viewBox="0 0 900 300" role="img" aria-label="Causal lines connect deployment, service, journey, and business impact">
      <path d="M120 60 C260 60 235 130 380 130 S530 210 650 210 S770 260 830 260" />
      <path class="faint" d="M110 245 C250 230 290 205 410 210 S610 100 820 95" />
    </svg>
  </div>
  <div class="outcome-strip"><span>query bound</span><span>cohort bound</span><span>action pending</span><span>outcome unverified</span></div>
</section>
""",
    "puriq-finance": """
<section class="stage research" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Thesis evidence graph</span><strong>research · not execution</strong></div>
  <div class="research-grid">
    <div class="filing-mosaic" aria-label="Synthetic filing evidence mosaic">
      <button type="button" data-node="10k" class="filing tall is-active"><small>10-K</small><b>risk factors</b><span>accession bound</span></button>
      <button type="button" data-node="8k" class="filing"><small>8-K</small><b>event</b><span>new evidence</span></button>
      <button type="button" data-node="facts" class="filing"><small>XBRL</small><b>company facts</b><span>period bound</span></button>
      <button type="button" data-node="counter" class="filing warning"><small>counter</small><b>thesis pressure</b><span>unresolved</span></button>
    </div>
    <div class="scenario-fan">
      <div class="scenario bull"><span>upside</span><b>assumptions 4</b></div>
      <div class="scenario base"><span>base</span><b>assumptions 6</b></div>
      <div class="scenario bear"><span>downside</span><b>assumptions 5</b></div>
      <div class="invalidation"><small>invalidation condition</small><strong>margin thesis breaks below bound</strong></div>
    </div>
  </div>
</section>
""",
    "terra": """
<section class="stage parcel" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Parcel strata</span><strong>time-aware civic twin</strong></div>
  <div class="parcel-layout">
    <div class="parcel-map" aria-label="Synthetic parcel map">
      <button class="lot lot-1" data-node="lot-1" type="button"><span>01</span></button>
      <button class="lot lot-2 is-active" data-node="lot-2" type="button"><span>02</span><small>selected</small></button>
      <button class="lot lot-3" data-node="lot-3" type="button"><span>03</span></button>
      <button class="lot lot-4" data-node="lot-4" type="button"><span>04</span></button>
      <button class="lot lot-5" data-node="lot-5" type="button"><span>05</span></button>
      <div class="contour contour-a" aria-hidden="true"></div><div class="contour contour-b" aria-hidden="true"></div>
    </div>
    <ol class="strata" aria-label="Parcel evidence strata">
      <li><small>2022</small><b>ownership source</b><span>observed</span></li>
      <li><small>2024</small><b>zoning delta</b><span>measured</span></li>
      <li><small>2025</small><b>built form</b><span>PLUTO revision</span></li>
      <li><small>scenario</small><b>opportunity</b><span>advisory</span></li>
    </ol>
  </div>
</section>
""",
    "prism-counsel": """
<section class="stage counsel" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Matter argument command</span><strong>review required</strong></div>
  <div class="counsel-grid">
    <div class="issue-prism" aria-label="Synthetic issue and argument lattice">
      <div class="prism-shape" aria-hidden="true"></div>
      <button type="button" data-node="record" class="prism-node record is-active"><small>record</small><b>fact</b></button>
      <button type="button" data-node="authority" class="prism-node authority"><small>authority</small><b>source</b></button>
      <button type="button" data-node="argument" class="prism-node argument"><small>argument</small><b>inference</b></button>
      <button type="button" data-node="counter" class="prism-node counter"><small>counter</small><b>unresolved</b></button>
    </div>
    <div class="authority-rail">
      <article><small>authority 01</small><b>Federal Register</b><span>source-linked</span></article>
      <article><small>authority 02</small><b>controlling record</b><span>operator-bound</span></article>
      <article class="deadline"><small>deadline</small><b>review date</b><span>source required</span></article>
      <div class="review-stamp">DRAFT · NOT APPROVED</div>
    </div>
  </div>
</section>
""",
    "living-anatomy": """
<section class="stage anatomy" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Living system body</span><strong>failure + recovery</strong></div>
  <div class="body-map" aria-label="Interactive synthetic software anatomy">
    <div class="body-spine" aria-hidden="true"></div>
    <button class="organ organ-brain is-active" data-node="brain" type="button"><small>YUYAY</small><b>brain</b><span>proposal</span></button>
    <button class="organ organ-heart" data-node="heart" type="button"><small>SONQO</small><b>heart</b><span>policy</span></button>
    <button class="organ organ-blood" data-node="blood" type="button"><small>YAWAR</small><b>circulation</b><span>receipts</span></button>
    <button class="organ organ-nerve" data-node="nerve" type="button"><small>WILLAY</small><b>nervous</b><span>events</span></button>
    <button class="organ organ-bone" data-node="bone" type="button"><small>TULLU</small><b>skeleton</b><span>invariants</span></button>
    <div class="circulation circulation-a" aria-hidden="true"></div><div class="circulation circulation-b" aria-hidden="true"></div>
  </div>
  <div class="injury-panel"><span>inject bounded injury</span><button type="button" data-injury="heart">heart down</button><button type="button" data-injury="blood">receipt tamper</button><strong>healthy remains advisory</strong></div>
</section>
""",
    "szl-atlas": """
<section class="stage atlas" aria-labelledby="stage-title" data-stage>
  <div class="stage-head"><span>Evidence atlas</span><strong>discover · inspect · verify</strong></div>
  <div class="atlas-field" aria-label="Public artifact constellation">
    <div class="atlas-orbit atlas-o1" aria-hidden="true"></div><div class="atlas-orbit atlas-o2" aria-hidden="true"></div>
    <div class="atlas-core"><span>SZL</span><strong>source bound</strong></div>
    <button type="button" data-node="models" class="artifact artifact-model is-active"><small>models</small><b>provider observed</b></button>
    <button type="button" data-node="kernels" class="artifact artifact-kernel"><small>kernels</small><b>artifact class</b></button>
    <button type="button" data-node="datasets" class="artifact artifact-data"><small>datasets</small><b>revision</b></button>
    <button type="button" data-node="spaces" class="artifact artifact-space"><small>Spaces</small><b>runtime state</b></button>
    <button type="button" data-node="evidence" class="artifact artifact-proof"><small>evidence</small><b>limitations</b></button>
  </div>
  <div class="source-beacon"><span>canonical source</span><strong>exact revision required</strong><span>HTTP 200 ≠ readiness</span></div>
</section>
""",
}


_BASE_CSS: Final[str] = r"""
:root{color-scheme:dark;--surface:#07090d;--elevated:#10141a;--text:#f4f1e8;--muted:#97a0aa;--accent:#d9e2ea;--accent2:#8e7cff;--danger:#d36b67;--line:color-mix(in oklab,var(--accent) 18%,transparent);font-family:var(--body,ui-sans-serif),system-ui,sans-serif}
*{box-sizing:border-box}html{background:var(--surface);color:var(--text);scroll-behavior:smooth}body{margin:0;min-width:320px;background:radial-gradient(90% 70% at 50% -10%,color-mix(in oklab,var(--accent2) 12%,transparent),transparent 68%),var(--surface)}button,a{font:inherit}button{color:inherit}.skip{position:fixed;left:1rem;top:-5rem;z-index:100;background:var(--text);color:var(--surface);padding:.75rem 1rem}.skip:focus{top:1rem}a{color:inherit}.shell{width:min(1180px,calc(100% - 2rem));margin:auto}.topbar{min-height:64px;display:flex;align-items:center;gap:1rem;border-bottom:1px solid var(--line)}.brand{font:600 1rem/1 var(--mono,ui-monospace);letter-spacing:.18em;text-decoration:none}.crumb{color:var(--muted);font-size:.85rem}.state{margin-left:auto;border:1px solid var(--line);padding:.4rem .65rem;border-radius:999px;color:var(--accent);font:600 .68rem/1 var(--mono,ui-monospace);letter-spacing:.08em}.hero{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(18rem,.95fr);gap:clamp(2rem,5vw,5rem);align-items:end;padding:clamp(3rem,8vw,7rem) 0 2rem}.eyebrow{font:600 .72rem/1.2 var(--mono,ui-monospace);letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}h1{font:400 clamp(3rem,7vw,6.6rem)/.9 var(--display,serif);letter-spacing:-.04em;margin:.35em 0 .25em}.lede{max-width:62ch;color:var(--muted);font-size:clamp(1rem,1.5vw,1.2rem)}.hero-note{border-left:1px solid var(--line);padding-left:1.25rem}.hero-note small{display:block;color:var(--muted);font:600 .68rem/1.4 var(--mono,ui-monospace);text-transform:uppercase;letter-spacing:.12em}.hero-note strong{display:block;font:400 clamp(1.4rem,3vw,2.4rem)/1.1 var(--display,serif);margin:.4rem 0}.stage{position:relative;min-height:clamp(32rem,64vw,44rem);overflow:hidden;border:1px solid var(--line);border-radius:1.5rem;background:linear-gradient(160deg,color-mix(in oklab,var(--accent) 5%,var(--elevated)),var(--surface));isolation:isolate}.stage:before{content:"";position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(180deg,transparent 0 5px,color-mix(in oklab,var(--accent) 3%,transparent) 6px);mix-blend-mode:screen}.stage-head{position:relative;z-index:10;display:flex;justify-content:space-between;gap:1rem;padding:1.1rem 1.25rem;border-bottom:1px solid var(--line);font:600 .68rem/1.3 var(--mono,ui-monospace);letter-spacing:.11em;text-transform:uppercase}.stage-head span{color:var(--muted)}.stage button{min-width:44px;min-height:44px;border:1px solid var(--line);background:color-mix(in oklab,var(--elevated) 88%,transparent);cursor:pointer;transition:border-color .18s ease,transform .18s ease,box-shadow .18s ease}.stage button:hover,.stage button:focus-visible,.stage button.is-active{border-color:var(--accent);box-shadow:0 0 1.5rem color-mix(in oklab,var(--accent) 17%,transparent);outline:none}.stage button:focus-visible{outline:2px solid var(--accent);outline-offset:3px}.stage button b,.stage button small,.stage button span{display:block}.stage button small{color:var(--muted);font:600 .62rem/1.3 var(--mono,ui-monospace);text-transform:uppercase;letter-spacing:.08em}.stage button b{font:500 1rem/1.2 var(--body,ui-sans-serif)}.stage button span{color:var(--muted);font-size:.7rem}.contract{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;padding:2rem 0 4rem}.contract article{border-top:1px solid var(--line);padding-top:1rem}.contract small{color:var(--accent);font:600 .68rem/1.3 var(--mono,ui-monospace);letter-spacing:.12em;text-transform:uppercase}.contract h2{font:400 1.5rem/1.1 var(--display,serif);margin:.45rem 0}.contract p,.contract li{color:var(--muted);font-size:.9rem}.contract ul{padding-left:1rem}.modules{display:flex;flex-wrap:wrap;gap:.5rem}.modules span{border:1px solid var(--line);padding:.45rem .65rem;border-radius:999px;color:var(--muted);font-size:.78rem}.footer{display:flex;gap:1rem;justify-content:space-between;border-top:1px solid var(--line);padding:1.5rem 0 3rem;color:var(--muted);font:500 .7rem/1.5 var(--mono,ui-monospace)}
/* A11oy */.trajectory-steps{position:absolute;inset:24% 5% auto;display:grid;grid-template-columns:repeat(6,1fr);gap:.65rem;padding:0;list-style:none}.trajectory-steps li{position:relative;min-height:9rem;border:1px solid var(--line);padding:1rem;background:color-mix(in oklab,var(--elevated) 90%,transparent)}.trajectory-steps b{color:var(--accent);font:600 .7rem var(--mono,ui-monospace)}.trajectory-steps span,.trajectory-steps small{display:block}.trajectory-steps span{margin-top:2rem;font:400 1.3rem var(--display,serif)}.trajectory-steps small{color:var(--muted);margin-top:.3rem}.trajectory-line{position:absolute;left:7%;right:7%;top:35%;height:1px;background:var(--accent);box-shadow:0 0 18px var(--accent)}.policy-chamber{position:absolute;left:8%;right:8%;bottom:8%;display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.policy-chamber div{background:var(--surface);padding:1rem}.policy-chamber small,.policy-chamber strong{display:block}.policy-chamber small{color:var(--muted);font:600 .65rem var(--mono,ui-monospace);text-transform:uppercase}.policy-chamber strong{margin-top:.4rem}
/* Hatun */.constellation .orbit{position:absolute;border:1px solid var(--line);border-radius:50%;left:50%;top:52%;transform:translate(-50%,-50%)}.orbit-one{width:54%;aspect-ratio:1}.orbit-two{width:78%;aspect-ratio:1}.star{position:absolute;width:8.5rem;border-radius:50%;aspect-ratio:1}.star-intent{left:10%;top:24%}.star-evidence{left:33%;top:13%}.star-decision{right:30%;top:20%}.star-commitment{right:9%;top:45%}.star-outcome{left:22%;bottom:8%}.council-core{position:absolute;left:50%;top:52%;transform:translate(-50%,-50%);width:11rem;aspect-ratio:1;border:1px solid var(--accent);border-radius:50%;display:grid;place-content:center;text-align:center;background:var(--surface);box-shadow:0 0 3rem color-mix(in oklab,var(--accent) 20%,transparent)}.council-core span,.council-core strong,.council-core small{display:block}.council-core span{font:600 .7rem var(--mono,ui-monospace);letter-spacing:.18em}.council-core strong{font:400 1.25rem var(--display,serif);margin:.3rem}.council-core small{color:var(--accent)}
/* Killinchu */.radar-field{position:absolute;inset:13% 7% 12%;overflow:hidden;border:1px solid var(--line);border-radius:50%;background:radial-gradient(circle,color-mix(in oklab,var(--accent) 7%,transparent),transparent 58%)}.radar-ring{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);border:1px solid var(--line);border-radius:50%}.ring-a{width:28%;aspect-ratio:1}.ring-b{width:56%;aspect-ratio:1}.ring-c{width:84%;aspect-ratio:1}.radar-sweep{position:absolute;left:50%;top:50%;width:45%;height:1px;transform-origin:left;background:linear-gradient(90deg,var(--accent),transparent);animation:sweep 7s linear infinite}.track{position:absolute;padding:.65rem .8rem}.track-a{left:64%;top:22%}.track-b{left:24%;top:62%}.track-c{left:71%;top:66%}.rules-ring{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);text-align:center}.rules-ring span,.rules-ring strong{display:block}.rules-ring span{color:var(--muted);font:600 .6rem var(--mono,ui-monospace);text-transform:uppercase}.rules-ring strong{color:var(--danger);margin-top:.3rem}.mission-clock{position:absolute;left:8%;right:8%;bottom:4%;display:flex;justify-content:space-between;color:var(--muted);font:600 .68rem var(--mono,ui-monospace)}@keyframes sweep{to{transform:rotate(360deg)}}
/* Sentra */.nerve-map{position:absolute;inset:18% 7% 16%}.nerve-node{position:absolute;width:9.5rem;padding:.8rem}.node-kev{left:2%;top:34%}.node-edge{left:25%;top:15%}.node-identity{left:44%;top:54%}.node-control{right:22%;top:20%}.node-impact{right:1%;top:49%}.nerve{position:absolute;height:2px;background:linear-gradient(90deg,var(--accent),var(--accent2));transform-origin:left;box-shadow:0 0 12px var(--accent)}.edge-1{left:13%;top:45%;width:21%;transform:rotate(-20deg)}.edge-2{left:35%;top:31%;width:20%;transform:rotate(30deg)}.edge-3{left:54%;top:60%;width:20%;transform:rotate(-29deg)}.edge-4{left:72%;top:37%;width:20%;transform:rotate(25deg)}.proof-stack{position:absolute;left:7%;right:7%;bottom:5%;display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem}.proof-stack span{border-top:1px solid var(--line);padding-top:.65rem;color:var(--muted);font-size:.72rem}
/* Lyte */.river{position:absolute;inset:16% 4% 13%;border-left:1px solid var(--line);border-bottom:1px solid var(--line)}.river-labels{position:absolute;inset:0 auto 0 0;display:grid;grid-template-rows:repeat(4,1fr);transform:translateX(-.2rem);color:var(--muted);font:600 .58rem var(--mono,ui-monospace);text-transform:uppercase}.trace{position:absolute;padding:.7rem .8rem;z-index:3}.trace-deploy{left:7%;top:8%}.trace-api{left:33%;top:31%}.trace-journey{left:58%;top:58%}.trace-impact{right:2%;bottom:2%}.river-lines{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.river-lines path{fill:none;stroke:var(--accent);stroke-width:3;filter:drop-shadow(0 0 8px var(--accent))}.river-lines path.faint{stroke:var(--accent2);stroke-width:1;opacity:.4}.outcome-strip{position:absolute;left:5%;right:5%;bottom:4%;display:flex;justify-content:space-between;color:var(--muted);font:600 .62rem var(--mono,ui-monospace)}
/* PURIQ */.research-grid{position:absolute;inset:16% 5% 8%;display:grid;grid-template-columns:1.1fr .9fr;gap:1rem}.filing-mosaic{display:grid;grid-template-columns:repeat(2,1fr);grid-auto-rows:1fr;gap:.7rem}.filing{padding:1rem;text-align:left}.filing.tall{grid-row:span 2}.filing.warning{border-color:var(--danger)}.filing span{margin-top:2rem}.scenario-fan{display:grid;gap:.65rem;align-content:center}.scenario{border-left:3px solid var(--accent);padding:1rem;background:var(--elevated);transform:skewX(-4deg)}.scenario span,.scenario b{display:block}.scenario span{color:var(--muted);font:600 .62rem var(--mono,ui-monospace);text-transform:uppercase}.scenario.bear{border-color:var(--danger)}.invalidation{margin-top:1rem;border:1px solid var(--danger);padding:1rem}.invalidation small,.invalidation strong{display:block}.invalidation small{color:var(--danger);font:600 .62rem var(--mono,ui-monospace);text-transform:uppercase}
/* Terra */.parcel-layout{position:absolute;inset:16% 5% 8%;display:grid;grid-template-columns:1.2fr .8fr;gap:1rem}.parcel-map{position:relative;display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);gap:.45rem;transform:rotate(-2deg);background:repeating-linear-gradient(20deg,transparent 0 28px,var(--line) 29px 30px)}.lot{position:relative;border-radius:.4rem;background:color-mix(in oklab,var(--elevated) 80%,transparent)!important}.lot-2{grid-row:span 2}.lot-4{grid-column:span 2}.lot small{margin-top:.4rem}.contour{position:absolute;border:1px solid var(--accent2);border-radius:45%;pointer-events:none;opacity:.45}.contour-a{inset:12% 18% 25% 9%}.contour-b{inset:30% 8% 8% 35%}.strata{list-style:none;padding:0;margin:0;display:grid;align-content:center}.strata li{display:grid;grid-template-columns:4rem 1fr auto;gap:1rem;border-top:1px solid var(--line);padding:1rem 0}.strata small{color:var(--accent);font:600 .62rem var(--mono,ui-monospace)}.strata span{color:var(--muted);font-size:.75rem}
/* Counsel */.counsel-grid{position:absolute;inset:16% 5% 8%;display:grid;grid-template-columns:1fr 1fr;gap:2rem}.issue-prism{position:relative}.prism-shape{position:absolute;inset:12% 13%;clip-path:polygon(50% 0,100% 92%,0 92%);border:1px solid var(--accent);background:linear-gradient(135deg,color-mix(in oklab,var(--accent) 12%,transparent),transparent)}.prism-node{position:absolute;width:9rem;padding:.8rem}.prism-node.record{left:5%;bottom:9%}.prism-node.authority{right:5%;bottom:9%}.prism-node.argument{left:38%;top:8%}.prism-node.counter{right:2%;top:42%}.authority-rail{display:grid;align-content:center;gap:.7rem}.authority-rail article{border-top:1px solid var(--line);padding:1rem}.authority-rail small,.authority-rail b,.authority-rail span{display:block}.authority-rail small{color:var(--accent);font:600 .62rem var(--mono,ui-monospace);text-transform:uppercase}.authority-rail span{color:var(--muted);font-size:.75rem}.authority-rail .deadline{border-color:var(--danger)}.review-stamp{border:1px solid var(--danger);color:var(--danger);padding:1rem;text-align:center;font:700 .72rem var(--mono,ui-monospace);letter-spacing:.15em;transform:rotate(-2deg)}
/* Anatomy */.body-map{position:absolute;inset:14% 12% 16%}.body-spine{position:absolute;left:50%;top:4%;bottom:4%;width:2px;background:linear-gradient(var(--accent),var(--accent2));box-shadow:0 0 20px var(--accent)}.organ{position:absolute;width:10rem;border-radius:50%;aspect-ratio:1}.organ-brain{left:50%;top:0;transform:translateX(-50%)}.organ-heart{left:50%;top:30%;transform:translateX(-50%)}.organ-blood{left:18%;top:45%}.organ-nerve{right:18%;top:45%}.organ-bone{left:50%;bottom:0;transform:translateX(-50%)}.circulation{position:absolute;border:1px solid var(--accent);border-radius:50%;opacity:.45}.circulation-a{inset:28% 9% 17%}.circulation-b{inset:38% 26% 7%}.injury-panel{position:absolute;left:5%;right:5%;bottom:4%;display:flex;align-items:center;gap:.6rem;color:var(--muted);font:600 .62rem var(--mono,ui-monospace);text-transform:uppercase}.injury-panel button{padding:.5rem .7rem;background:transparent}.injury-panel strong{margin-left:auto;color:var(--accent)}.stage.is-injured .organ-heart,.stage.is-tampered .organ-blood{border-color:var(--danger);box-shadow:0 0 2rem color-mix(in oklab,var(--danger) 30%,transparent)}
/* Atlas */.atlas-field{position:absolute;inset:14% 7% 12%}.atlas-orbit{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);border:1px solid var(--line);border-radius:50%}.atlas-o1{width:44%;aspect-ratio:1}.atlas-o2{width:78%;aspect-ratio:1}.atlas-core{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:9rem;aspect-ratio:1;border-radius:50%;display:grid;place-content:center;text-align:center;border:1px solid var(--accent);background:var(--surface);box-shadow:0 0 3rem color-mix(in oklab,var(--accent) 20%,transparent)}.atlas-core span,.atlas-core strong{display:block}.atlas-core span{font:600 1.2rem var(--mono,ui-monospace);letter-spacing:.2em}.atlas-core strong{color:var(--muted);font-size:.7rem}.artifact{position:absolute;width:9rem;padding:.8rem}.artifact-model{left:5%;top:20%}.artifact-kernel{left:18%;bottom:9%}.artifact-data{right:19%;bottom:5%}.artifact-space{right:4%;top:21%}.artifact-proof{left:50%;top:3%;transform:translateX(-50%)}.source-beacon{position:absolute;left:7%;right:7%;bottom:4%;display:flex;justify-content:space-between;color:var(--muted);font:600 .62rem var(--mono,ui-monospace)}.source-beacon strong{color:var(--accent)}
@media(max-width:800px){.hero{grid-template-columns:1fr}.hero-note{border-left:0;border-top:1px solid var(--line);padding:1rem 0}.stage{min-height:42rem}.contract{grid-template-columns:1fr}.trajectory-steps{grid-template-columns:repeat(2,1fr);top:14%}.trajectory-line{display:none}.trajectory-steps li{min-height:6.5rem}.trajectory-steps span{margin-top:.8rem}.policy-chamber{bottom:3%}.research-grid,.parcel-layout,.counsel-grid{grid-template-columns:1fr}.research-grid{inset:13% 4% 5%}.scenario-fan{grid-template-columns:repeat(3,1fr)}.invalidation{grid-column:1/-1}.parcel-layout{inset:14% 4% 5%}.parcel-map{min-height:18rem}.counsel-grid{inset:14% 4% 4%}.issue-prism{min-height:22rem}.authority-rail{grid-template-columns:repeat(2,1fr)}.review-stamp{grid-column:1/-1}.nerve-map{transform:scale(.78);transform-origin:center}.proof-stack{grid-template-columns:repeat(2,1fr)}.body-map{inset:13% 2% 18%}.organ-blood{left:2%}.organ-nerve{right:2%}.atlas-field{inset:12% 0 13%}.footer,.mission-clock,.outcome-strip,.source-beacon{flex-direction:column;align-items:flex-start;gap:.35rem}}
@media(max-width:520px){.shell{width:min(100% - 1rem,1180px)}h1{font-size:3rem}.stage{border-radius:1rem}.stage-head{align-items:flex-start;flex-direction:column}.policy-chamber{grid-template-columns:1fr}.constellation .orbit{display:none}.star{width:7.2rem}.star-intent{left:3%}.star-evidence{left:38%;top:12%}.star-decision{right:2%;top:28%}.star-commitment{right:4%;top:57%}.star-outcome{left:7%;bottom:8%}.council-core{width:8rem}.radar-field{inset:15% 1% 15%}.track{font-size:.78rem}.nerve-map{transform:scale(.62)}.trace{font-size:.75rem}.river-labels{display:none}.scenario-fan{grid-template-columns:1fr}.invalidation{grid-column:auto}.authority-rail{grid-template-columns:1fr}.organ{width:7.5rem}.organ-blood{top:48%}.organ-nerve{top:48%}.artifact{width:7rem;font-size:.75rem}.atlas-o2{width:96%}.atlas-o1{width:58%}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{animation:none!important;transition:none!important}.radar-sweep{display:none}}
"""


_INTERACTION_JS: Final[str] = r"""
(() => {
  const stage = document.querySelector('[data-stage]');
  if (!stage) return;
  stage.addEventListener('click', (event) => {
    const target = event.target.closest('[data-node]');
    if (target) {
      stage.querySelectorAll('[data-node]').forEach((node) => node.classList.remove('is-active'));
      target.classList.add('is-active');
      const output = document.querySelector('[data-selection]');
      if (output) output.textContent = target.dataset.node + ' · selected for evidence inspection';
      return;
    }
    const injury = event.target.closest('[data-injury]');
    if (!injury) return;
    const name = injury.dataset.injury;
    if (name === 'heart') stage.classList.toggle('is-injured');
    if (name === 'blood') stage.classList.toggle('is-tampered');
    const output = document.querySelector('[data-selection]');
    if (output) output.textContent = name + ' · bounded simulation toggled; no production state changed';
  });
})();
"""


def _style_tokens(spec: VerticalSpec) -> str:
    tokens = spec.theme.tokens
    return ";".join(
        (
            f"--surface:{tokens['surface']}",
            f"--elevated:{tokens['surface_elevated']}",
            f"--text:{tokens['text']}",
            f"--muted:{tokens['muted']}",
            f"--accent:{tokens['accent']}",
            f"--accent2:{tokens['accent_secondary']}",
            f"--danger:{tokens['danger']}",
            f"--display:'{escape(spec.theme.display_font)}'",
            f"--body:'{escape(spec.theme.body_font)}'",
            f"--mono:'{escape(spec.theme.mono_font)}'",
        )
    )


def render_vertical_showcase(vertical_id: str) -> str:
    """Render an original dependency-free front-end concept for one vertical."""

    spec = get_vertical(vertical_id)
    stage = _STAGE[vertical_id]
    modules = "".join(f"<span>{escape(item)}</span>" for item in spec.experience_modules)
    evidence = "".join(f"<li>{escape(item)}</li>" for item in spec.evidence_contract)
    signatures = "".join(f"<li>{escape(item)}</li>" for item in spec.theme.signature_modules)
    title = escape(spec.display_name)
    return f"""<!doctype html>
<html lang="en" data-vertical="{escape(spec.id)}" style="{_style_tokens(spec)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="description" content="{escape(spec.operator_outcome)}">
  <title>{title} · SZL Vertical Frontier</title>
  <style>{_BASE_CSS}</style>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<header class="shell topbar">
  <a class="brand" href="../">SZL / FRONTIER</a>
  <span class="crumb">{title}</span>
  <span class="state">{escape(spec.effect_mode.value)}</span>
</header>
<main class="shell" id="main">
  <section class="hero">
    <div>
      <p class="eyebrow">{escape(spec.product_class.replace('_', ' '))}</p>
      <h1 id="stage-title">{title}</h1>
      <p class="lede">{escape(spec.operator_outcome)}</p>
    </div>
    <aside class="hero-note" aria-label="Product distinction">
      <small>Unmet need</small>
      <strong>{escape(spec.unmet_need)}</strong>
      <small>Original SZL edge</small>
      <p>{escape(spec.differentiator)}</p>
    </aside>
  </section>
  {stage}
  <p class="eyebrow" aria-live="polite" data-selection>select an object to inspect its evidence state</p>
  <section class="contract" aria-label="Experience and evidence contract">
    <article><small>Experience modules</small><h2>Operator path</h2><div class="modules">{modules}</div></article>
    <article><small>Signature interactions</small><h2>Distinct by design</h2><ul>{signatures}</ul></article>
    <article><small>Evidence contract</small><h2>Proof at the decision</h2><ul>{evidence}</ul></article>
  </section>
</main>
<footer class="shell footer">
  <span>Public actuation: {escape(spec.public_actuation.value)}</span>
  <span>Model proposes · independent policy decides · human binds consequential action</span>
  <span>Λ uniqueness: Conjecture 1 — open</span>
</footer>
<script>{_INTERACTION_JS}</script>
</body>
</html>"""


def render_showcase_index() -> str:
    cards = []
    for spec in VERTICALS:
        cards.append(
            f"""<a class="card" href="./{escape(spec.id)}" style="--card-accent:{escape(spec.theme.tokens['accent'])}">
<span>{escape(spec.product_class.replace('_', ' '))}</span><h2>{escape(spec.display_name)}</h2>
<p>{escape(spec.operator_outcome)}</p><strong>{escape(spec.theme.signature_modules[0])} →</strong></a>"""
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SZL Vertical Frontier</title><style>
:root{{color-scheme:dark;font-family:ui-sans-serif,system-ui;background:#05070b;color:#f3f0e8}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(80% 50% at 50% 0,#111a2c,#05070b 68%)}}main{{width:min(1180px,calc(100% - 2rem));margin:auto;padding:4rem 0}}.eyebrow{{font:600 .7rem ui-monospace;letter-spacing:.16em;text-transform:uppercase;color:#8fa4bf}}h1{{font:400 clamp(3rem,8vw,7rem)/.9 Georgia,serif;letter-spacing:-.05em;margin:.25em 0}}.lede{{max-width:65ch;color:#9ca6b2;font-size:1.1rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(17rem,1fr));gap:1rem;margin-top:3rem}}.card{{min-height:18rem;display:flex;flex-direction:column;padding:1.25rem;border:1px solid color-mix(in oklab,var(--card-accent) 25%,transparent);border-radius:1.2rem;background:linear-gradient(150deg,color-mix(in oklab,var(--card-accent) 9%,#0b0e14),#080a0f);color:inherit;text-decoration:none;transition:transform .18s ease,border-color .18s ease}}.card:hover,.card:focus-visible{{transform:translateY(-3px);border-color:var(--card-accent);outline:2px solid var(--card-accent);outline-offset:3px}}.card span{{font:600 .62rem ui-monospace;letter-spacing:.1em;color:var(--card-accent)}}.card h2{{font:400 2rem Georgia,serif;margin:.5rem 0}}.card p{{color:#9ca6b2}}.card strong{{margin-top:auto;color:var(--card-accent);font-size:.85rem}}@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}</style></head><body><main><p class="eyebrow">SZL Holdings · executable experience contracts</p><h1>Ten products.<br>Ten distinct lanes.</h1><p class="lede">Original front-end concepts generated from one governed Python contract. Presentation never mints authority; each vertical preserves its own operator object, evidence chain, and effect boundary.</p><section class="grid">{''.join(cards)}</section></main></body></html>"""


def create_showcase_router():
    """Create optional FastAPI HTML routes for the executable design concepts."""

    try:
        from fastapi import APIRouter, HTTPException
        from fastapi.responses import HTMLResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required to create the showcase router") from exc

    router = APIRouter(prefix="/vertical-frontier", tags=["vertical-frontier-showcase"])

    @router.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_showcase_index()

    @router.get("/{vertical_id}", response_class=HTMLResponse)
    def vertical(vertical_id: str) -> str:
        try:
            return render_vertical_showcase(vertical_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
