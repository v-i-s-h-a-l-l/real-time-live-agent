/**
 * Toyota Voice Showroom — UI + shared VoiceAgent wiring.
 */

class AutomotiveVoiceAgent extends VoiceAgent {
  constructor(wsBaseUrl, ui) {
    super(wsBaseUrl);
    this.ui = ui;
    this._pendingChipHint = null;
  }

  connect(lang = 'en-IN') {
    return super.connect(lang, { agent: 'automotive' });
  }

  _setStatus(state, label) {
    const pill = this.ui.statusPill;
    pill.className = `voice-status-pill ${state}`;
    pill.querySelector('.status-label').textContent = label;
    this.ui.orb.className = `voice-orb ${state}`;
  }

  _appendTranscript(role, text) {
    if (!text?.trim()) return;
    const empty = this.ui.transcriptBody.querySelector('.transcript-empty');
    if (empty) empty.remove();

    const el = document.createElement('div');
    el.className = `msg ${role}`;
    const meta =
      role === 'user' ? 'You' : role === 'assistant' ? 'Toyota Assistant' : 'System';
    el.innerHTML = `<div class="msg-meta">${meta}</div>${escapeHtml(text)}`;
    this.ui.transcriptBody.appendChild(el);
    this.ui.transcriptBody.scrollTop = this.ui.transcriptBody.scrollHeight;
  }

  _updateContextStrip() {
    const connected = this.isConnected ? 'Connected' : 'Offline';
    this.ui.contextStrip.innerHTML =
      `<strong>${connected}</strong> · Model: <strong>${this.ui.selectedModel}</strong>`;
  }

  suggestHint(hint) {
    if (!this.isConnected) {
      this._pendingChipHint = hint;
      document.getElementById('voice')?.scrollIntoView({ behavior: 'smooth' });
      this.ui.voiceHint.textContent =
        'Start a voice session first, then ask: "' + hint + '"';
      return;
    }
    this._appendTranscript('system', `Try asking: "${hint}"`);
  }

  _onConnected() {
    this._setStatus('listening', 'Listening');
    this.ui.connectBtn.disabled = true;
    this.ui.disconnectBtn.disabled = false;
    this.ui.langSelect.disabled = true;
    this.ui.chips.forEach((c) => (c.disabled = false));
    this.ui.voiceHint.textContent =
      'Speak naturally — specs, brochure, service, finance, test drive, parts, warranty, or nearest dealer.';
    this._updateContextStrip();
    this._appendTranscript('system', 'Toyota voice assistant connected.');

    if (this._pendingChipHint) {
      this._appendTranscript('system', `Try asking: "${this._pendingChipHint}"`);
      this._pendingChipHint = null;
    }
  }

  _onDisconnected() {
    this._setStatus('', 'Offline');
    this.ui.connectBtn.disabled = false;
    this.ui.disconnectBtn.disabled = true;
    this.ui.langSelect.disabled = false;
    this.ui.chips.forEach((c) => (c.disabled = true));
    this.ui.voiceHint.textContent = 'Tap Start Voice Session to speak with our Toyota assistant.';
    this._updateContextStrip();
    this._appendTranscript('system', 'Session ended.');
  }

  _onBotStartedSpeaking() {
    this._setStatus('speaking', 'Speaking');
  }

  _onBotStoppedSpeaking() {
    this._setStatus('listening', 'Listening');
  }

  _onTranscription(text) {
    if (!text?.trim()) return;
    this._appendTranscript('user', text);
    const lower = text.toLowerCase();
    for (const [key, name] of Object.entries(MODEL_KEYWORDS)) {
      if (lower.includes(key)) {
        selectModel(this.ui, name);
        break;
      }
    }
  }

  _onThinking() {
    this._setStatus('thinking', 'Thinking');
  }

  _onError(data) {
    this._setStatus('', 'Error');
    const msg = data?.message || 'Something went wrong';
    this.ui.voiceHint.textContent = msg;
    this._appendTranscript('system', `Error: ${msg}`);
  }
}

const MODEL_KEYWORDS = {
  fortuner: 'Fortuner',
  innova: 'Innova Crysta',
  crysta: 'Innova Crysta',
  hyryder: 'Hyryder',
  'urban cruiser': 'Hyryder',
  camry: 'Camry',
  glanza: 'Glanza',
  hilux: 'Hilux',
};

const QUICK_CHIPS = [
  {
    label: 'Specs & price',
    desc: 'Technical details & variants',
    hint: 'What are the specs and price of Fortuner Legender diesel automatic?',
  },
  {
    label: 'Brochure Q&A',
    desc: 'Features from official brochure',
    hint: 'Tell me about Hyryder hybrid features from the brochure',
  },
  {
    label: 'Book service',
    desc: 'Schedule appointment',
    hint: 'I need to book a Toyota service appointment for next Saturday',
  },
  {
    label: 'Service checklist',
    desc: 'General service report',
    hint: 'What is included in a 20,000 km service for Innova Crysta?',
  },
  {
    label: 'Finance & EMI',
    desc: 'Loan & down payment',
    hint: 'What is the EMI on Fortuner 4x4 AT for 7 years with 5 lakh down?',
  },
  {
    label: 'Test drive',
    desc: 'Book this weekend',
    hint: 'I want to test drive the Camry hybrid this weekend',
  },
  {
    label: 'Parts & accessories',
    desc: 'Compatible parts',
    hint: 'I need floor mats and alloy wheels for my 2023 Fortuner',
  },
  {
    label: 'Warranty help',
    desc: 'Coverage & claims',
    hint: 'What does my Toyota extended warranty cover?',
  },
  {
    label: 'Nearest dealer',
    desc: 'Find showroom near you',
    hint: 'Which is the nearest Toyota dealer to Sector 29 Gurugram?',
  },
  {
    label: 'Exchange car',
    desc: 'Trade-in valuation',
    hint: 'I want to exchange my old car for a new Hyryder',
  },
];

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function selectModel(ui, name) {
  ui.selectedModel = name;
  ui.modelCards.forEach((card) => {
    card.classList.toggle('selected', card.dataset.model === name);
  });
  if (ui.agent) ui.agent._updateContextStrip();
}

/* ── Hero carousel ── */
function initCarousel() {
  const track = document.getElementById('carousel-track');
  const dotsContainer = document.getElementById('carousel-dots');
  const slides = track.querySelectorAll('.carousel-slide');
  let index = 0;
  let timer = null;
  const total = slides.length;

  slides.forEach((_, i) => {
    const dot = document.createElement('button');
    dot.type = 'button';
    dot.className = 'carousel-dot' + (i === 0 ? ' active' : '');
    dot.setAttribute('aria-label', `Slide ${i + 1}`);
    dot.addEventListener('click', () => goTo(i));
    dotsContainer.appendChild(dot);
  });

  const dots = dotsContainer.querySelectorAll('.carousel-dot');

  function goTo(i) {
    index = ((i % total) + total) % total;
    track.style.transform = `translateX(-${index * 100}%)`;
    dots.forEach((d, j) => d.classList.toggle('active', j === index));
  }

  function next() {
    goTo(index + 1);
  }

  function startAutoplay() {
    stopAutoplay();
    timer = setInterval(next, 5500);
  }

  function stopAutoplay() {
    if (timer) clearInterval(timer);
  }

  document.getElementById('carousel-prev').addEventListener('click', () => {
    goTo(index - 1);
    startAutoplay();
  });
  document.getElementById('carousel-next').addEventListener('click', () => {
    next();
    startAutoplay();
  });

  track.addEventListener('mouseenter', stopAutoplay);
  track.addEventListener('mouseleave', startAutoplay);

  startAutoplay();
}

/* ── Scroll reveal ── */
function initScrollReveal() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          observer.unobserve(e.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
  );
  document.querySelectorAll('.reveal').forEach((el) => observer.observe(el));
}

function initAutomotiveApp() {
  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsBase = `${wsProtocol}//${location.host}/ws`;

  const ui = {
    orb: document.getElementById('voice-orb'),
    statusPill: document.getElementById('status-pill'),
    voiceHint: document.getElementById('voice-hint'),
    connectBtn: document.getElementById('connect-btn'),
    disconnectBtn: document.getElementById('disconnect-btn'),
    langSelect: document.getElementById('lang-select'),
    transcriptBody: document.getElementById('transcript-body'),
    contextStrip: document.getElementById('context-strip'),
    modelCards: document.querySelectorAll('.model-card'),
    chips: [],
    selectedModel: 'Fortuner',
  };

  const agent = new AutomotiveVoiceAgent(wsBase, ui);
  ui.agent = agent;

  ui.connectBtn.addEventListener('click', () => agent.connect(ui.langSelect.value));
  ui.disconnectBtn.addEventListener('click', () => agent.disconnect());

  ui.modelCards.forEach((card) => {
    const activate = () => {
      selectModel(ui, card.dataset.model);
      if (agent.isConnected) {
        agent._appendTranscript(
          'system',
          `Selected ${card.dataset.model}. Try: "Tell me about the ${card.dataset.model}"`
        );
      }
    };
    card.addEventListener('click', activate);
    card.querySelector('.model-cta')?.addEventListener('click', (e) => {
      e.stopPropagation();
      activate();
      document.getElementById('voice')?.scrollIntoView({ behavior: 'smooth' });
    });
  });

  const chipsContainer = document.getElementById('chips-grid');
  QUICK_CHIPS.forEach((chip) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.disabled = true;
    btn.innerHTML = `<span class="chip-label">${chip.label}</span><span class="chip-desc">${chip.desc}</span>`;
    btn.addEventListener('click', () => agent.suggestHint(chip.hint));
    chipsContainer.appendChild(btn);
    ui.chips.push(btn);
  });

  document.querySelectorAll('[data-hint]').forEach((el) => {
    el.addEventListener('click', (e) => {
      const hint = el.getAttribute('data-hint');
      if (hint) {
        e.preventDefault();
        agent.suggestHint(hint);
      }
    });
  });

  document.getElementById('fab-test-drive')?.addEventListener('click', () =>
    agent.suggestHint('I want to book a test drive for Fortuner this weekend')
  );
  document.getElementById('fab-brochure')?.addEventListener('click', () =>
    agent.suggestHint('Can I get the brochure for Innova Crysta top variant?')
  );
  document.getElementById('fab-price')?.addEventListener('click', () =>
    agent.suggestHint('What is the on-road price of Hyryder hybrid top model?')
  );

  document.getElementById('menu-toggle')?.addEventListener('click', () => {
    document.getElementById('utility-nav')?.classList.toggle('mobile-open');
  });

  selectModel(ui, 'Fortuner');
  initCarousel();
  initScrollReveal();
}

document.addEventListener('DOMContentLoaded', initAutomotiveApp);
