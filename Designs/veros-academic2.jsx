// Veros — A2: Refined Academic direction
// Iteration on A: less cluttered, calmer stats, more whitespace, same arxiv DNA.

// ─────────────────────────────────────────────────────────────
// Landing — calm, hero-led, stats relegated to a small footer band
// ─────────────────────────────────────────────────────────────
function LandingAcademic2() {
  return (
    <div className="ab" style={{
      width: '100%', height: '100%', overflow: 'hidden',
      background: '#fbf8f1', color: '#1c1815',
      fontFamily: '"Newsreader", Georgia, serif', position: 'relative',
    }}>
      {/* Slim, single nav — no sub-tagline bar this time */}
      <div style={{ background: '#7a1c1c', color: '#f5e7e0', padding: '12px 48px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: 'Inter, sans-serif', fontSize: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <VerosMark size={18} color="#f5e7e0"/>
          <strong style={{ letterSpacing: 0.4 }}>Veros</strong>
        </div>
        <div style={{ display: 'flex', gap: 28, opacity: 0.92 }}>
          <span>Browse</span><span>Methodology</span><span>API</span>
          <span style={{ borderLeft: '1px solid rgba(255,255,255,0.25)', paddingLeft: 28 }}>Sign in</span>
        </div>
      </div>

      {/* Hero — generously spaced, single column */}
      <div style={{ padding: '120px 96px 0', maxWidth: 980 }}>
        <div style={{ fontSize: 11, letterSpacing: 2.5, textTransform: 'uppercase', color: '#7a1c1c', fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>
          Open peer review, distilled
        </div>
        <h1 style={{ fontSize: 76, lineHeight: 1.02, margin: '20px 0 0', fontWeight: 400, letterSpacing: -1.6, maxWidth: 880 }}>
          Read the papers <em style={{ color: '#7a1c1c', fontStyle: 'italic' }}>worth reading.</em>
        </h1>
        <p style={{ fontSize: 19, lineHeight: 1.55, color: '#4a4038', maxWidth: 600, marginTop: 22, fontFamily: '"Newsreader", serif' }}>
          Veros aggregates every reviewer comment on OpenReview, weights consensus, and tells you which sections deserve your hour.
        </p>

        {/* Search — single, clean, no offset shadow */}
        <div style={{ marginTop: 40, display: 'flex', alignItems: 'stretch', maxWidth: 720, border: '1.5px solid #1c1815', background: '#fff' }}>
          <div style={{ padding: '0 18px', display: 'flex', alignItems: 'center', color: '#5a4a32' }}>
            <VIcon name="search" size={18}/>
          </div>
          <input
            placeholder="Paper title, arXiv ID, or OpenReview link"
            style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', padding: '20px 0', fontSize: 17, fontFamily: '"Newsreader", serif', color: '#1c1815' }}
          />
          <button style={{ background: '#7a1c1c', color: '#fff', border: 'none', padding: '0 32px', fontSize: 14, fontFamily: 'Inter, sans-serif', fontWeight: 500, letterSpacing: 0.6, cursor: 'pointer' }}>
            Verify
          </button>
        </div>

        {/* Examples — quieter, smaller */}
        <div style={{ marginTop: 14, fontSize: 13, color: '#7a6a55', fontFamily: 'Inter, sans-serif' }}>
          Try <span style={{ color: '#7a1c1c', textDecoration: 'underline', cursor: 'pointer' }}>arXiv:2402.09876</span>, <span style={{ color: '#7a1c1c', textDecoration: 'underline', cursor: 'pointer' }}>"Sparse Autoencoders"</span>, or paste a forum URL.
        </div>
      </div>

      {/* Stats — small footer band, inline prose-style, NOT a 4-up grid */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, borderTop: '1px solid #d6cab2', padding: '20px 96px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: 'Inter, sans-serif', fontSize: 13, color: '#5a4a32' }}>
          <div>
            Indexing <strong style={{ color: '#1c1815', fontFamily: '"Newsreader", serif', fontSize: 16, fontWeight: 500 }}>847,329</strong> papers across <strong style={{ color: '#1c1815', fontFamily: '"Newsreader", serif', fontSize: 16, fontWeight: 500 }}>142</strong> venues
            &nbsp;·&nbsp; <strong style={{ color: '#1c1815', fontFamily: '"Newsreader", serif', fontSize: 16, fontWeight: 500 }}>2.4M</strong> reviewer comments parsed.
          </div>
          <div style={{ fontFamily: '"IBM Plex Mono", monospace', fontSize: 11, color: '#7a6a55' }}>last sync 04/25/26 06:41 UTC</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Search — quieter table, no double-bordered chunky cells
// ─────────────────────────────────────────────────────────────
function SearchAcademic2() {
  const [q, setQ] = React.useState('language model');
  return (
    <div className="ab" style={{
      width: '100%', height: '100%', overflow: 'hidden',
      background: '#fbf8f1', color: '#1c1815',
      fontFamily: '"Newsreader", Georgia, serif',
    }}>
      <div style={{ background: '#7a1c1c', color: '#f5e7e0', padding: '12px 48px', display: 'flex', alignItems: 'center', gap: 28, fontFamily: 'Inter, sans-serif', fontSize: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <VerosMark size={18} color="#f5e7e0"/>
          <strong>Veros</strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'stretch', background: '#fff', flex: 1, maxWidth: 540, height: 32 }}>
          <input value={q} onChange={e => setQ(e.target.value)} style={{ flex: 1, border: 'none', outline: 'none', padding: '0 12px', fontSize: 13, fontFamily: 'inherit', color: '#1c1815' }}/>
          <button style={{ background: '#1c1815', color: '#fff', border: 'none', padding: '0 16px', fontSize: 12, cursor: 'pointer' }}>Search</button>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 22 }}><span>Browse</span><span>API</span><span>Sign in</span></div>
      </div>

      {/* Results header — softer */}
      <div style={{ padding: '36px 64px 6px' }}>
        <h1 style={{ fontSize: 26, margin: 0, fontWeight: 500, letterSpacing: -0.3 }}>
          Results for <em style={{ color: '#7a1c1c' }}>"{q}"</em>
        </h1>
        <div style={{ marginTop: 6, fontFamily: 'Inter, sans-serif', fontSize: 13, color: '#7a6a55' }}>
          4,217 papers · sorted by Veros score
        </div>
      </div>

      <div style={{ padding: '0 64px', overflow: 'auto', height: 'calc(100% - 168px)' }}>
        {VEROS_PAPERS.map((p, i) => {
          const sc = p.score >= 7 ? '#0f5132' : p.score >= 5 ? '#7a5f00' : '#7a1c1c';
          return (
            <div key={p.id} style={{
              display: 'grid', gridTemplateColumns: '78px 1fr 130px',
              padding: '20px 0', borderTop: i === 0 ? '1px solid #d6cab2' : 'none',
              borderBottom: '1px solid #ede5d6', gap: 20, cursor: 'pointer',
            }}>
              {/* Score column — quiet, single number */}
              <div>
                <div style={{ fontSize: 30, color: sc, fontWeight: 500, lineHeight: 1, letterSpacing: -0.5 }}>{p.score.toFixed(1)}</div>
                <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', color: '#7a6a55', marginTop: 4 }}>{p.grade}</div>
              </div>
              <div>
                <div style={{ fontSize: 17, fontWeight: 500, lineHeight: 1.3, color: '#7a1c1c' }}>{p.title}</div>
                <div style={{ fontSize: 12, color: '#5a4a32', fontFamily: 'Inter, sans-serif', marginTop: 4 }}>{p.authors}</div>
                <div style={{ fontSize: 13, color: '#3a3530', marginTop: 8, lineHeight: 1.55, maxWidth: 720, fontStyle: 'italic' }}>{p.tldr}</div>
                <div style={{ marginTop: 8, fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', color: '#7a6a55' }}>arxiv:{p.id} · {p.venue} · {p.citations} citations</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10 }}>
                <VerdictPill verdict={p.verdict}/>
                <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', color: '#7a6a55' }}>consensus<br/><span style={{ color: '#1c1815' }}>{p.consensus.split(' · ')[0]} ×{p.consensus.split(' · ').length}</span></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Paper — calm, balanced. Score panel is smaller, more whitespace.
// ─────────────────────────────────────────────────────────────
function PaperAcademic2() {
  const p = VEROS_PAPERS[0];
  return (
    <div className="ab" style={{
      width: '100%', height: '100%', overflow: 'auto',
      background: '#fbf8f1', color: '#1c1815',
      fontFamily: '"Newsreader", Georgia, serif',
    }}>
      <div style={{ background: '#7a1c1c', color: '#f5e7e0', padding: '12px 48px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: 'Inter, sans-serif', fontSize: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <VerosMark size={18} color="#f5e7e0"/>
          <strong>Veros</strong>
        </div>
        <div style={{ display: 'flex', gap: 22 }}><span>Browse</span><span>API</span><span>Sign in</span></div>
      </div>

      <div style={{ padding: '36px 96px 60px', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ fontSize: 12, fontFamily: 'Inter, sans-serif', color: '#7a6a55' }}>
          <span style={{ color: '#7a1c1c', cursor: 'pointer' }}>← Back to results</span> &nbsp;·&nbsp; arxiv:{p.id}
        </div>

        {/* Title */}
        <h1 style={{ fontSize: 38, fontWeight: 500, lineHeight: 1.15, margin: '20px 0 0', letterSpacing: -0.5, maxWidth: 880 }}>{p.title}</h1>
        <div style={{ marginTop: 10, fontSize: 14, color: '#3a3530', fontStyle: 'italic' }}>{p.authors}</div>
        <div style={{ marginTop: 6, fontSize: 12, fontFamily: '"IBM Plex Mono", monospace', color: '#7a6a55' }}>{p.venue} · {p.citations} citations · accepted (oral)</div>

        {/* Score row — single horizontal band, no boxy panel */}
        <div style={{ marginTop: 30, paddingTop: 24, paddingBottom: 24, borderTop: '1.5px solid #1c1815', borderBottom: '1px solid #d6cab2', display: 'grid', gridTemplateColumns: '180px 1fr 200px', gap: 32, alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', letterSpacing: 1.5, textTransform: 'uppercase', color: '#7a6a55' }}>Veros Score</div>
            <div style={{ fontSize: 64, fontWeight: 500, lineHeight: 1, color: '#0f5132', marginTop: 4, letterSpacing: -2 }}>{p.score.toFixed(1)}</div>
            <div style={{ fontSize: 13, fontFamily: 'Inter, sans-serif', color: '#5a4a32', marginTop: 2 }}>grade {p.grade} · out of 10</div>
          </div>
          <div>
            {[['Novelty', p.novelty], ['Technical', p.technical], ['Clarity', p.clarity], ['Impact', p.impact]].map(([l, v]) => (
              <div key={l} style={{ marginBottom: 8, display: 'grid', gridTemplateColumns: '90px 1fr 40px', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 13, fontFamily: 'Inter, sans-serif', color: '#5a4a32' }}>{l}</span>
                <div style={{ height: 4, background: '#ede5d6' }}>
                  <div style={{ width: `${v}%`, height: '100%', background: '#7a1c1c' }}/>
                </div>
                <span style={{ fontSize: 12, fontFamily: '"IBM Plex Mono", monospace', color: '#1c1815', textAlign: 'right' }}>{v}</span>
              </div>
            ))}
          </div>
          <div style={{ textAlign: 'right' }}>
            <VerdictPill verdict={p.verdict}/>
            <div style={{ fontSize: 12, fontFamily: 'Inter, sans-serif', color: '#5a4a32', marginTop: 10 }}>4 reviewers · consensus <strong style={{ color: '#0f5132' }}>strong</strong></div>
          </div>
        </div>

        {/* TL;DR — just prose, no card */}
        <div style={{ marginTop: 32 }}>
          <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', letterSpacing: 1.5, textTransform: 'uppercase', color: '#7a6a55' }}>AI-distilled summary</div>
          <p style={{ fontSize: 19, lineHeight: 1.6, marginTop: 8, marginBottom: 0, maxWidth: 820 }}>{p.tldr}</p>
        </div>

        {/* Read / Skim — clean two columns, no boxes */}
        <div style={{ marginTop: 32, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40 }}>
          <div>
            <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', letterSpacing: 1.5, textTransform: 'uppercase', color: '#0f5132', fontWeight: 600, paddingBottom: 8, borderBottom: '1.5px solid #0f5132' }}>Read deeply</div>
            <ul style={{ margin: '12px 0 0', paddingLeft: 18, fontSize: 15, lineHeight: 1.85 }}>
              {p.deep.map(s => <li key={s}>{s}</li>)}
            </ul>
          </div>
          <div>
            <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', letterSpacing: 1.5, textTransform: 'uppercase', color: '#7a5f00', fontWeight: 600, paddingBottom: 8, borderBottom: '1.5px solid #7a5f00' }}>Skim or skip</div>
            <ul style={{ margin: '12px 0 0', paddingLeft: 18, fontSize: 15, lineHeight: 1.85, color: '#5a4a32' }}>
              {p.skim.map(s => <li key={s}>{s}</li>)}
            </ul>
          </div>
        </div>

        {/* Reviewer voices — quieter, more breathing room */}
        <div style={{ marginTop: 36, paddingTop: 22, borderTop: '1.5px solid #1c1815' }}>
          <div style={{ fontSize: 11, fontFamily: 'Inter, sans-serif', letterSpacing: 1.5, textTransform: 'uppercase', color: '#7a6a55', marginBottom: 14 }}>What reviewers said · {p.consensus}</div>
          {[
            { r: 'Reviewer xY3p', score: 'Strong Accept · 9/10', q: 'The compute-optimal scaling analysis in §4.4 is the most rigorous treatment of conditional computation I\'ve seen in two years.' },
            { r: 'Reviewer t4Kw', score: 'Accept · 8/10', q: 'Routing analysis is novel; related-work coverage in §5 is thin. Does not change my recommendation.' },
            { r: 'Reviewer m9aE', score: 'Weak Accept · 7/10', q: 'Solid work. Clarity in §3 could be improved — equations 11–14 are under-explained.' },
          ].map(rv => (
            <div key={rv.r} style={{ paddingTop: 14, paddingBottom: 14, borderBottom: '1px solid #ede5d6' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontFamily: 'Inter, sans-serif', color: '#5a4a32' }}>
                <span>{rv.r}</span>
                <span style={{ color: '#7a1c1c', fontWeight: 600 }}>{rv.score}</span>
              </div>
              <p style={{ fontSize: 15, lineHeight: 1.6, margin: '6px 0 0', fontStyle: 'italic' }}>"{rv.q}"</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LandingAcademic2, SearchAcademic2, PaperAcademic2 });
