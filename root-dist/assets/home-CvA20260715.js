(function(){const n=document.createElement("link").relList;if(n&&n.supports&&n.supports("modulepreload"))return;for(const a of document.querySelectorAll('link[rel="modulepreload"]'))i(a);new MutationObserver(a=>{for(const s of a)if(s.type==="childList")for(const o of s.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&i(o)}).observe(document,{childList:!0,subtree:!0});function t(a){const s={};return a.integrity&&(s.integrity=a.integrity),a.referrerPolicy&&(s.referrerPolicy=a.referrerPolicy),a.crossOrigin==="use-credentials"?s.credentials="include":a.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function i(a){if(a.ep)return;a.ep=!0;const s=t(a);fetch(a.href,s)}})();function r(e,n){return n}const k=[{id:"evalai",name:"EvalAI",badge:"Evaluation",href:r(void 0,"/evalai/"),apiBaseUrl:r(void 0,"/api/evalai/"),description:"Automate assignment/case-study evaluation. Generate consistent scores and detailed feedback at scale.",backDescription:["Takes case study, rubric/keypoints, and student submissions, then scores answers using hybrid matching/scoring logic and generates Excel reports. It is mainly for structured academic/internal evaluation."],usage:"Only for internal Purpose",client:"",pills:["Case Study & Problem Statement","Rubric based Scoring","Reports"],icon:"clipboard"},{id:"comcoachai",name:"ComcoachAI",badge:"Communication",href:r(void 0,"/comcoachai"),apiBaseUrl:r(void 0,"/api/comcoachai/"),description:"Improve communication skills with quality feedback on  strengths and area of improvement in tone, clarity, and confidence.",backDescription:["Trainers create scenarios and rubrics; participants record audio responses. The backend transcribes speech, analyzes audio quality, evaluates the transcript with AI, gives scores, strengths, improvements, and report/dashboard data."],usage:"Used for",client:"communication skill assessment.",pills:["Speech Analysis","Rubric based Scores"," Strengths & Improvements"],icon:"message"},{id:"convai",name:"ConvAI",badge:"Conversation",href:r(void 0,"/convai/"),apiBaseUrl:r(void 0,"/api/convai/"),description:"Practise challenging workplace conversations with a realistic AI persona in a safe environment. Explore different approaches, receive personalized feedback, and build the confidence to handle similar situations effectively in the workplace.",backDescription:["Engage in realistic workplace conversations with an AI persona through voice or text. Practise situations such as giving feedback, managing conflict, coaching team members, and handling escalations, without real-world consequences. After each conversation, receive personalized insights into your communication style, strengths, and areas for improvement, along with practical recommendations to help you respond more effectively."],usage:"Used for",client:"Difficult conversational skill assessment.",pills:["Realistic Workplace Scenarios","Adaptive Conversations","Actionable feedback"],icon:"conversation"},{id:"survey360",name:"Survey 360",badge:"Assessment",href:"https://survey360.u-next.com",apiBaseUrl:"",description:"Collect structured feedback through Self, 270°, and 360° evaluations. Generate actionable insights on employee performance, competencies, and development areas.",backDescription:["Survey 360 enables organizations to collect structured feedback through Self, 270°, and 360° assessments across multiple stakeholders including managers, peers, and direct reports.","It aggregates responses to provide a comprehensive view of employee performance, competencies, and behavioral patterns."],usage:"Used for",client:"employee performance assessment.",pills:["Self Assessment","270° Feedback","360° Feedback"],icon:"clipboard"},{id:"careerinventory",name:"Career Inventory",badge:"Assessment",href:"https://survey.u-next.com",apiBaseUrl:"",description:"Identify career strengths, motivations, and ideal role alignment. Based on Career Anchor Assessment to improve fit and long-term satisfaction.",backDescription:["Career Inventory helps individuals understand their career drivers, strengths, and motivations using the Career Anchor Assessment framework.","It identifies eight key anchors including Autonomy, Challenge, Entrepreneurial Creativity, Managerial Competence, Lifestyle, Security, Service, and Technical Expertise.","The tool supports better career planning, role alignment, and long-term job satisfaction by matching individuals with suitable opportunities."],usage:"Used for",client:"career pathing and role alignment.",pills:["Career Guidance","Self Awareness","Career Planning"],icon:"conversation"},{id:"codeevaluation",name:"Code Evaluation",badge:"Technical",href:"https://fdeevaluatoragent-escotkya6v5bmw2ewnaybt.streamlit.app/",apiBaseUrl:"",description:"Assess coding skills through real-time challenges and practical tests. Measure problem-solving ability, logic, and programming efficiency.",backDescription:["Code Evaluation is designed to assess technical and programming skills through real-time coding challenges and practical problem-solving exercises.","It evaluates logic, efficiency, and coding standards across different difficulty levels and domains.","The system generates structured performance reports, helping organizations make data-driven hiring and skill assessment decisions."],usage:"Used for",client:"technical skill assessment.",pills:["Coding Tests","Problem Solving","Logic Evaluation"],icon:"clipboard"}],h={clipboard:`
    <svg viewBox="0 0 24 24" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
      <rect x="9" y="3" width="6" height="4" rx="2"/>
      <path d="M9 12h6M9 16h4"/>
    </svg>
  `,message:`
    <svg viewBox="0 0 24 24" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      <path d="M8 10h8M8 14h5"/>
    </svg>
  `,conversation:`
    <svg viewBox="0 0 24 24" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M17 8h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-2v4l-4-4H9a2 2 0 0 1-2-2v-1"/>
      <path d="M15 3H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2v4l4-4h4a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z"/>
    </svg>
  `,arrow:`
    <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M5 12h14M12 5l7 7-7 7"/>
    </svg>
  `};function v(e){return h[e]||h.arrow}const w=document.querySelector("#app");function g(e){return String(e).replaceAll("&","&amp;").replaceAll('"',"&quot;").replaceAll("<","&lt;").replaceAll(">","&gt;")}function A(e,n){var p,u;const t=e.pills.map(c=>`<span class="pill">${c}</span>`).join(""),i=e.backDescription.map(c=>`<span>${c}</span>`).join(""),a=(p=e.usage)==null?void 0:p.trim(),s=(u=e.client)==null?void 0:u.trim(),o=a?`
          <span class="usage-line" aria-label="${g([a,s].filter(Boolean).join(" "))}">
            <span>${a}</span>
            ${s?`<strong>${s}</strong>`:""}
          </span>
      `:"",f=e.status?`
            <span class="status status-${e.statusType??"default"}">
              <span class="status-dot"></span>
              <span>${e.status}</span>
            </span>
      `:"",b=[e.name,e.badge,e.description,a,s,...e.pills,...e.backDescription].filter(Boolean).join(" "),y=`${.34+n*.1}s`;return`
    <a
      class="card card-${e.id}"
      href="${e.href}"
      aria-label="Open ${e.name}"
      style="animation-delay: ${y}"
      data-tool-id="${e.id}"
      data-api-base-url="${e.apiBaseUrl}"
      data-search-text="${g(b.toLowerCase())}"
    >
      <span class="card-inner">
        <span class="card-face card-front">
          <span class="card-badge">${e.badge}</span>
          <span class="card-main">
            <span class="card-icon">${v(e.icon)}</span>
            <span class="card-title">${e.name}</span>
            <span class="card-desc">${e.description}</span>
            ${o}
            <span class="card-pills">${t}</span>
          </span>
          <span class="card-cta">
            ${f}
            <span class="cta-arrow">${v("arrow")}</span>
          </span>
        </span>
        <span class="card-face card-back">
          <span class="card-back-content">
            <span class="card-back-kicker">${e.badge}</span>
            <span class="card-back-title">${e.name}</span>
            <span class="card-back-desc">${i}</span>
          </span>
        </span>
      </span>
    </a>
  `}w.innerHTML=`
  <div class="bg-stage" aria-hidden="true">
    <div class="bg-top-glow"></div>
    <div class="stripe stripe-1"></div>
    <div class="stripe stripe-2"></div>
    <div class="stripe stripe-3"></div>
  </div>

  <div class="wrapper">
    <header class="top-nav">
      <a class="logo-group" href="/" aria-label="EvalTools home">
        <span class="logo-mark" aria-hidden="true">
          <img src="/unext-mark.svg" alt="" />
        </span>
        <div class="logo-divider"></div>
        <div class="logo-product">
          <span class="logo-product-name">EvalTools</span>
          <span class="logo-product-sub">AI Suite</span>
        </div>
      </a>
      <label class="search-shell" aria-label="Search tools">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m21 21-4.35-4.35"/>
          <circle cx="11" cy="11" r="7"/>
        </svg>
        <input type="search" placeholder="Search tools" />
      </label>
      <div class="nav-actions" aria-label="Account actions">
        <button class="icon-button" type="button" aria-label="Settings">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z"/>
            <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.87l-.06-.06A2 2 0 1 1 7.07 4.24l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.2.62.77 1 1.42 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1Z"/>
          </svg>
        </button>
      </div>
    </header>

    <main>
      <section class="hero" aria-labelledby="page-title">
        <div class="hero-kicker">EvalTools - Innovation Hub</div>
        <h1 id="page-title">Innovation <em>Hub</em></h1>
        <p>One platform to access all training, evaluation, coaching, and simulation experiences.</p>
      </section>

      <p class="section-label">Choose a tool</p>
      <section class="cards" aria-label="AI tools">
        ${k.map(A).join("")}
      </section>
      <p class="empty-search" hidden>No tools match your search.</p>

      <section class="support-section" aria-labelledby="support-title">
        <div class="support-copy">
          <span class="section-chip">Enterprise support</span>
          <h2 id="support-title">Reach out to our team for any assistance</h2>
          <p>We are here to assist with any questions or feedback. Complete the form, and we will reply as soon as possible.</p>
        </div>
        <div class="support-panel">
          <aside class="contact-card" aria-label="Contact information">
            <h3>Contact Information</h3>
            <div class="contact-list">
              <div class="contact-row">
                <span class="contact-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.35 1.89.7 2.81a2 2 0 0 1-.45 2.11L8.1 9.9a16 16 0 0 0 6 6l1.26-1.26a2 2 0 0 1 2.11-.45c.92.35 1.85.58 2.81.7A2 2 0 0 1 22 16.92Z"/></svg>
                </span>
                <div><span>Phone</span><strong>+91 8431877399</strong></div>
              </div>
              <div class="contact-row">
                <span class="contact-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="m22 6-10 7L2 6"/></svg>
                </span>
                <div><span>Email</span><strong>ashutosh.yadav@u-next.com</strong></div>
              </div>
              <div class="contact-row">
                <span class="contact-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 4.99-5.53 10.2-7.32 11.56a1.1 1.1 0 0 1-1.36 0C9.53 20.2 4 14.99 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
                </span>
                <div>
                  <span>Address</span>
                  <strong>UNext Learning Pvt. Ltd.</strong>
                  <p>1/1, UNext Towers, Swami Vivekananda Road, Near Trinity Circle, Bengaluru, Karnataka 560008</p>
                </div>
              </div>
            </div>
          </aside>

          <!-- contact form removed per request; only contact information card is shown -->
        </div>
      </section>
    </main>
  </div>

  <footer>
    <div class="wrapper">
    <color mode="dark" class="footer-logo" aria-hidden="true">
      <span class="footer-line">&copy; 2026 <strong>U-Next</strong> . EvalTools Platform . Internal tools</span>
    </div>
  </footer>
`;const l=document.querySelector(".search-shell input"),d=[...document.querySelectorAll(".card")],m=document.querySelector(".empty-search"),C=window.matchMedia("(hover: hover) and (pointer: fine)").matches;l==null||l.addEventListener("input",e=>{const n=e.target.value.trim().toLowerCase();let t=0;d.forEach(i=>{const a=i.dataset.searchText.includes(n);i.classList.toggle("is-filtered",!a),i.setAttribute("aria-hidden",String(!a)),a&&(t+=1)}),m&&(m.hidden=t>0)});if(!C){const e=new Set(["survey360","careerinventory","codeevaluation"]);d.forEach(n=>{n.addEventListener("click",t=>{e.has(n.dataset.toolId)||n.classList.contains("is-flipped")||(t.preventDefault(),d.forEach(i=>{i!==n&&i.classList.remove("is-flipped")}),n.classList.add("is-flipped"))})})}
