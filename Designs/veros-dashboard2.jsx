// Veros — C2: Refined Dashboard direction
// Iteration on C: drop the heavy terminal aesthetic, keep the data-richness.
// Light theme, sans + mono accents only, scientific dashboard look.

const C2 = {
  bg: '#f6f4ef',
  surface: '#ffffff',
  border: '#e3ddd0',
  borderStrong: '#c8c0ac',
  text: '#1c1916',
  muted: '#6f6657',
  red: '#7a1c1c',
  redBg: '#fbeeec',
  green: '#1f6b3f',
  amber: '#9a6c00',
};

// ─────────────────────────────────────────────────────────────
// Landing — calm scientific dashboard, search front-and-center,
// data accents on the side without the dark terminal vibe.
// ─────────────────────────────────────────────────────────────
function LandingDashboard2() {
  return (
    <div className="ab" style={{
      width: '100%', height: '100%', overflow: 'hidden',
      background: C2.bg, color: C2.text,
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      {/* Slim top nav with mono accents */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 32px', borderBottom: `1px solid ${C2.border}`, background: C2.surface }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <VerosMark size={18} color={C2.red}/>
          <strong style={{ fontSize: 15, letterSpacing: -0.2 }}>Veros</strong>
          <span style={{ marginLeft: 12, fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1 }}>v0.4 · BETA</span>
        </div>
        <div style={{ display: 'flex', gap: 26, fontSize: 13, color: '#3a3530' }}>
          <span>Browse</span><span>Methodology</span><span>API</span><span>Docs</span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', color: C2.green, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: C2.green }}/>SYNC OK
          </span>
          <button style={{ background: C2.red, color: '#fff', border: 'none', padding: '7px 14px', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Sign in</button>
        </div>
      </div>

      {/* Body grid: hero + side panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', height: 'calc(100% - 51px)' }}>
        {/* Hero */}
        <div style={{ padding: '76px 64px 40px', borderRight: `1px solid ${C2.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', letterSpacing: 1.8, color: C2.red, fontWeight: 600 }}>
            REVIEWER-GROUNDED PAPER QUALITY
          </div>
          <h1 style={{ fontSize: 72, lineHeight: 1.02, margin: '20px 0 0', fontWeight: 600, letterSpacing: -2.4, color: C2.text }}>
            Quality, <span style={{ color: C2.red }}>verified.</span>
          </h1>
          <p style={{ fontSize: 18, color: '#3a3530', maxWidth: 560, lineHeight: 1.55, marginTop: 22, fontWeight: 400 }}>
            Every paper scored from the actual peer reviews on OpenReview — with section-level guidance for what to read, skim, or skip.
          </p>

          {/* Search — light, scientific, NOT a terminal */}
          <div style={{ marginTop: 36, maxWidth: 680, background: C2.surface, border: `1px solid ${C2.borderStrong}`, padding: 6, display: 'flex', alignItems: 'center' }}>
            <span style={{ padding: '0 14px 0 12px', color: C2.muted, fontFamily: '"IBM Plex Mono", monospace', fontSize: 12, letterSpacing: 1, borderRight: `1px solid ${C2.border}` }}>QUERY</span>
            <input
              placeholder="arXiv ID · paper title · OpenReview URL"
              style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', padding: '14px 14px', fontSize: 15, color: C2.text }}
            />
            <button style={{ background: C2.red, color: '#fff', border: 'none', padding: '10px 20px', fontSize: 13, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              Verify <VIcon name="arrow" size={14} stroke="#fff"/>
            </button>
          </div>
          <div style={{ marginTop: 12, fontSize: 12, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted }}>
            try: arxiv:2402.09876 · "mixture of depths" · openreview.net/forum?id=...
          </div>

          {/* Inline mini-stats — scientific, restrained */}
          <div style={{ marginTop: 'auto', paddingTop: 36, borderTop: `1px solid ${C2.border}`, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24 }}>
            {[
              ['847,329', 'papers indexed'],
              ['2.4M', 'reviews parsed'],
              ['142', 'venues'],
              ['1,284', 'scored today'],
            ].map(([n, l]) => (
              <div key={l}>
                <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.8 }}>{n}</div>
                <div style={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1, marginTop: 4 }}>{l.toUpperCase()}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Side rail — score distribution + recent verifications */}
        <div style={{ padding: '24px 24px', display: 'flex', flexDirection: 'column', gap: 22, background: C2.bg }}>
          {/* Score distribution */}
          <div style={{ background: C2.surface, border: `1px solid ${C2.border}`, padding: '16px 18px' }}>
            <div style={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', letterSpacing: 1.5, color: C2.muted, marginBottom: 12 }}>SCORE DISTRIBUTION · 24H</div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 90 }}>
              {[8, 12, 19, 28, 41, 57, 73, 89, 71, 52, 38, 22, 14, 8, 4].map((h, i) => (
                <div key={i} style={{ flex: 1, height: `${h}%`, background: i >= 6 && i <= 11 ? C2.red : '#d6cebc' }}/>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: C2.muted, marginTop: 6, fontFamily: '"IBM Plex Mono", monospace' }}>
              <span>0.0</span><span>median 6.34</span><span>10.0</span>
            </div>
          </div>

          {/* Recent verifications */}
          <div style={{ background: C2.surface, border: `1px solid ${C2.border}`, padding: '14px 16px', flex: 1 }}>
            <div style={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', letterSpacing: 1.5, color: C2.muted, marginBottom: 12 }}>RECENTLY VERIFIED</div>
            {VEROS_PAPERS.slice(0, 5).map((p, i) => {
              const sc = p.score >= 7 ? C2.green : p.score >= 5 ? C2.amber : C2.red;
              return (
                <div key={p.id} style={{ display: 'grid', gridTemplateColumns: '36px 1fr', gap: 10, padding: '10px 0', borderTop: i === 0 ? 'none' : `1px solid ${C2.border}`, alignItems: 'center' }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: sc, fontFamily: '"IBM Plex Mono", monospace' }}>{p.score.toFixed(1)}</span>
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ fontSize: 12, color: C2.text, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{p.title}</div>
                    <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, marginTop: 2 }}>{p.venue}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Search — scientific dashboard table, light theme
// ─────────────────────────────────────────────────────────────
function SearchDashboard2() {
  return (
    <div className="ab" style={{
      width: '100%', height: '100%', overflow: 'hidden',
      background: C2.bg, color: C2.text,
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      {/* Top */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, padding: '14px 32px', borderBottom: `1px solid ${C2.border}`, background: C2.surface }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <VerosMark size={18} color={C2.red}/>
          <strong style={{ fontSize: 15, letterSpacing: -0.2 }}>Veros</strong>
        </div>
        <div style={{ flex: 1, maxWidth: 580, background: C2.bg, border: `1px solid ${C2.border}`, display: 'flex', alignItems: 'center', height: 36, marginLeft: 24 }}>
          <span style={{ padding: '0 12px', color: C2.muted, fontFamily: '"IBM Plex Mono", monospace', fontSize: 11, letterSpacing: 1, borderRight: `1px solid ${C2.border}` }}>QUERY</span>
          <input defaultValue="mixture of experts" style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', padding: '0 12px', fontSize: 13 }}/>
          <button style={{ background: C2.red, color: '#fff', border: 'none', padding: '8px 14px', fontSize: 12, cursor: 'pointer' }}>Search</button>
        </div>
        <div style={{ marginLeft: 'auto', fontSize: 12, color: C2.muted }}>Sort by <strong style={{ color: C2.text }}>Veros score</strong></div>
      </div>

      {/* Sub-stats strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr) 1fr', gap: 0, borderBottom: `1px solid ${C2.border}`, background: C2.surface }}>
        {[
          ['Matches', '4,217'],
          ['Avg score', '6.34'],
          ['Worth Reading', '38%'],
          ['Years', '2018–26'],
        ].map(([l, v], i) => (
          <div key={l} style={{ padding: '14px 22px', borderRight: `1px solid ${C2.border}` }}>
            <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1.2 }}>{l.toUpperCase()}</div>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2, letterSpacing: -0.5 }}>{v}</div>
          </div>
        ))}
        <div style={{ padding: '14px 22px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10, fontSize: 12, color: C2.muted }}>
          <span>Filter:</span>
          <span style={{ padding: '4px 10px', border: `1px solid ${C2.border}`, fontSize: 11, fontFamily: '"IBM Plex Mono", monospace' }}>venue: ANY</span>
          <span style={{ padding: '4px 10px', border: `1px solid ${C2.border}`, fontSize: 11, fontFamily: '"IBM Plex Mono", monospace' }}>year: 2024–26</span>
          <span style={{ padding: '4px 10px', border: `1px solid ${C2.border}`, fontSize: 11, fontFamily: '"IBM Plex Mono", monospace' }}>score: ≥ 0</span>
        </div>
      </div>

      {/* Table header */}
      <div style={{ display: 'grid', gridTemplateColumns: '90px 70px 1fr 130px 130px 110px', gap: 16, padding: '10px 32px', fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1.2, borderBottom: `1px solid ${C2.border}`, background: C2.bg }}>
        <span>SCORE</span><span>GRADE</span><span>PAPER</span><span>VENUE</span><span>METRICS</span><span>VERDICT</span>
      </div>

      {/* Rows */}
      <div style={{ overflow: 'auto', height: 'calc(100% - 199px)' }}>
        {VEROS_PAPERS.map(p => {
          const sc = p.score >= 7 ? C2.green : p.score >= 5 ? C2.amber : C2.red;
          return (
            <div key={p.id} style={{
              display: 'grid', gridTemplateColumns: '90px 70px 1fr 130px 130px 110px', gap: 16,
              padding: '16px 32px', borderBottom: `1px solid ${C2.border}`, alignItems: 'flex-start',
              background: C2.surface, cursor: 'pointer',
            }}>
              <div>
                <div style={{ fontSize: 24, fontWeight: 600, color: sc, letterSpacing: -0.5, lineHeight: 1 }}>{p.score.toFixed(1)}</div>
                <div style={{ fontSize: 10, color: C2.muted, fontFamily: '"IBM Plex Mono", monospace', marginTop: 4 }}>/ 10.0</div>
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, fontFamily: '"IBM Plex Mono", monospace' }}>{p.grade}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3 }}>{p.title}</div>
                <div style={{ fontSize: 12, color: C2.muted, marginTop: 4 }}>{p.authors}</div>
                <div style={{ fontSize: 12, color: '#3a3530', marginTop: 6, lineHeight: 1.5 }}>{p.tldr}</div>
              </div>
              <div style={{ fontSize: 12, color: '#3a3530' }}>
                <div style={{ fontWeight: 500 }}>{p.venue}</div>
                <div style={{ fontFamily: '"IBM Plex Mono", monospace', fontSize: 10, color: C2.muted, marginTop: 4 }}>arxiv:{p.id}</div>
              </div>
              <div>
                {[['nov', p.novelty], ['tech', p.technical], ['imp', p.impact]].map(([l, v]) => (
                  <div key={l} style={{ display: 'grid', gridTemplateColumns: '32px 1fr 24px', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted }}>{l}</span>
                    <div style={{ height: 3, background: '#ede5d6' }}>
                      <div style={{ width: `${v}%`, height: '100%', background: C2.red }}/>
                    </div>
                    <span style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', textAlign: 'right' }}>{v}</span>
                  </div>
                ))}
              </div>
              <div><VerdictPill verdict={p.verdict}/></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Paper — scientific dashboard with KPI tiles, but light & calm
// ─────────────────────────────────────────────────────────────
function PaperDashboard2() {
  const p = VEROS_PAPERS[0];
  return (
    <div className="ab" style={{
      width: '100%', height: '100%', overflow: 'auto',
      background: C2.bg, color: C2.text,
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      {/* Top nav */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 32px', borderBottom: `1px solid ${C2.border}`, background: C2.surface }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <VerosMark size={18} color={C2.red}/>
          <strong style={{ fontSize: 15 }}>Veros</strong>
          <span style={{ fontSize: 12, color: C2.muted }}>← back to results</span>
        </div>
        <div style={{ fontSize: 12, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted }}>arxiv:{p.id} · openreview ↗</div>
      </div>

      <div style={{ padding: '28px 48px 48px', maxWidth: 1180, margin: '0 auto' }}>
        {/* Title */}
        <div style={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', color: C2.red, letterSpacing: 1.5, fontWeight: 600 }}>PAPER · {p.venue}</div>
        <h1 style={{ fontSize: 28, fontWeight: 600, lineHeight: 1.2, margin: '6px 0 0', letterSpacing: -0.4, maxWidth: 920 }}>{p.title}</h1>
        <div style={{ marginTop: 6, fontSize: 13, color: C2.muted }}>{p.authors}</div>

        {/* KPI grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr', gap: 12, marginTop: 24 }}>
          {/* Big score */}
          <div style={{ background: C2.surface, border: `1px solid ${C2.border}`, padding: '20px 22px' }}>
            <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1.5 }}>VEROS_SCORE</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6 }}>
              <span style={{ fontSize: 56, color: C2.green, fontWeight: 600, letterSpacing: -2, lineHeight: 1 }}>{p.score.toFixed(1)}</span>
              <span style={{ fontSize: 16, color: C2.muted }}>/ 10</span>
            </div>
            <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
              <VerdictPill verdict={p.verdict}/>
              <span style={{ fontSize: 12, color: C2.muted }}>grade <strong style={{ color: C2.text }}>{p.grade}</strong></span>
            </div>
          </div>
          {[['NOVELTY', p.novelty], ['TECHNICAL', p.technical], ['CLARITY', p.clarity], ['IMPACT', p.impact]].map(([l, v]) => (
            <div key={l} style={{ background: C2.surface, border: `1px solid ${C2.border}`, padding: '20px 22px' }}>
              <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1.5 }}>{l}</div>
              <div style={{ fontSize: 36, fontWeight: 600, marginTop: 6, letterSpacing: -1, lineHeight: 1 }}>{v}<span style={{ fontSize: 14, color: C2.muted, fontWeight: 400 }}>/100</span></div>
              <div style={{ height: 3, background: '#ede5d6', marginTop: 14 }}>
                <div style={{ width: `${v}%`, height: '100%', background: C2.red }}/>
              </div>
            </div>
          ))}
        </div>

        {/* TL;DR */}
        <div style={{ marginTop: 14, background: C2.surface, border: `1px solid ${C2.border}`, padding: '18px 22px' }}>
          <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.red, letterSpacing: 1.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <VIcon name="spark" size={11} stroke={C2.red}/> AI_DISTILL · summary
          </div>
          <p style={{ margin: '10px 0 0', fontSize: 16, lineHeight: 1.6, color: '#1a1815' }}>{p.tldr}</p>
        </div>

        {/* Read / Skim grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
          <div style={{ background: C2.surface, border: `1px solid ${C2.border}`, padding: '18px 22px' }}>
            <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.green, letterSpacing: 1.5, fontWeight: 600 }}>READ_DEEPLY · {p.deep.length} sections</div>
            <ul style={{ margin: '12px 0 0', padding: 0, listStyle: 'none' }}>
              {p.deep.map(s => (
                <li key={s} style={{ padding: '8px 0', borderBottom: `1px solid ${C2.border}`, fontSize: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: C2.green }}/>{s}
                </li>
              ))}
            </ul>
          </div>
          <div style={{ background: C2.surface, border: `1px solid ${C2.border}`, padding: '18px 22px' }}>
            <div style={{ fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.amber, letterSpacing: 1.5, fontWeight: 600 }}>SKIM_OR_SKIP · {p.skim.length} sections</div>
            <ul style={{ margin: '12px 0 0', padding: 0, listStyle: 'none' }}>
              {p.skim.map(s => (
                <li key={s} style={{ padding: '8px 0', borderBottom: `1px solid ${C2.border}`, fontSize: 14, display: 'flex', alignItems: 'center', gap: 10, color: C2.muted }}>
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: C2.amber }}/>{s}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Reviewers panel */}
        <div style={{ marginTop: 12, background: C2.surface, border: `1px solid ${C2.border}` }}>
          <div style={{ padding: '12px 22px', borderBottom: `1px solid ${C2.border}`, fontSize: 10, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted, letterSpacing: 1.5, display: 'flex', justifyContent: 'space-between' }}>
            <span>REVIEWERS · 4 OFFICIAL</span>
            <span style={{ color: C2.green }}>CONSENSUS_STRENGTH: HIGH (σ = 0.71)</span>
          </div>
          {[
            ['xY3p', 9, 'Strong Accept', 'Most rigorous treatment of conditional computation in two years.'],
            ['t4Kw', 8, 'Accept', 'Routing analysis novel. Related-work coverage thin.'],
            ['m9aE', 7, 'Weak Accept', 'Clarity in §3 could be improved.'],
            ['p2Lq', 8, 'Accept', 'Reproducibility checklist complete; code released.'],
          ].map(([r, s, v, q], i) => (
            <div key={r} style={{ display: 'grid', gridTemplateColumns: '90px 50px 130px 1fr', gap: 16, padding: '14px 22px', borderBottom: i < 3 ? `1px solid ${C2.border}` : 'none', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontFamily: '"IBM Plex Mono", monospace', color: C2.muted }}>r/{r}</span>
              <span style={{ fontSize: 16, fontWeight: 600, color: C2.green, fontFamily: '"IBM Plex Mono", monospace' }}>{s}/10</span>
              <span style={{ fontSize: 13, color: C2.text, fontWeight: 500 }}>{v}</span>
              <span style={{ fontSize: 14, color: '#3a3530', lineHeight: 1.5 }}>"{q}"</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LandingDashboard2, SearchDashboard2, PaperDashboard2 });
