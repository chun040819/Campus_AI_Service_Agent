import { useRef, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Trace = { step: number; tool_name: string; arguments: unknown; result: unknown };
type Turn = { question: string; reply: string; tool_traces: Trace[] };

const examples = [
  ['操作指引', 'API Key 要怎麼申請？', 'API Key 怎麼申請？'],
  ['錯誤排查', '遇到 429，該怎麼辦？', '429 代表什麼？'],
  ['故障紀錄', '查詢 INC-001 的處理進度', 'INC-001 處理到哪？'],
  ['次數試算', '每日 20 次，已用 8 次，還剩多少？', '假設每日20次，今天已用8次，還剩多少？'],
  ['人工協助', '一直無法登入，想找人協助', '一直無法登入，想找人工'],
];

function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h15m-6-6 6 6-6 6'} /></svg>;
}

function ToolTraces({ traces }: { traces: Trace[] }) {
  return <details className="trace-group">
    <summary>
      <svg className="trace-symbol" aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M5 4v10h14m-5-5 5 5-5 5" /></svg>
      <span>工具執行紀錄</span><span className="trace-count">{traces.length} 次呼叫</span>
      <svg className="chevron" aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="m6 9 6 6 6-6" /></svg>
    </summary>
    <div className="trace-content">
      {traces.length === 0 ? <p className="muted">本輪未執行工具。</p> : traces.map((trace, index) => <details className="trace" key={index} open>
        <summary><span className="step-number">{String(index + 1).padStart(2, '0')}</span><span>{trace.tool_name}</span><span className="muted">步驟 {trace.step}</span></summary>
        <div className="trace-columns">
          <div><h3>呼叫參數</h3><pre>{JSON.stringify(trace.arguments, null, 2)}</pre></div>
          <div><h3>執行結果</h3><pre>{JSON.stringify(trace.result, null, 2)}</pre></div>
        </div>
      </details>)}
    </div>
  </details>;
}

function App() {
  const [session, setSession] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function chooseExample(question: string) {
    setMessage(question);
    inputRef.current?.focus();
    inputRef.current?.scrollIntoView({ block: 'nearest' });
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!message.trim() || busy) return;
    setBusy(true); setError('');
    const question = message.trim();
    try {
      const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: session, message: question }) });
      const body = await response.json();
      if (!response.ok && !body.reply) throw new Error(typeof body.detail === 'string' ? body.detail : '請求失敗，請稍後重試。');
      setSession(body.session_id);
      setTurns(previous => [...previous, { question, reply: body.reply, tool_traces: body.tool_traces }]);
      setMessage('');
      if (!response.ok) setError('模型未完成本輪回覆，對話歷史未新增此輪；可重試或清除。');
    } catch (cause) { setError(cause instanceof TypeError ? '連線失敗，請確認網路後再試。' : cause instanceof Error ? cause.message : '連線失敗，請稍後重試。'); }
    finally { setBusy(false); }
  }

  async function reset() {
    setBusy(true); setError('');
    try {
      if (session) {
        const response = await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: session }) });
        if (!response.ok) throw new Error('清除失敗，請重試。');
      }
      setSession(null); setTurns([]); setMessage('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : '清除失敗'); }
    finally { setBusy(false); }
  }

  return <>
    <a className="skip-link" href="#message">跳至問題輸入</a>
    <header className="site-header"><div className="brand"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M5 25V9l11-4 11 4v16M11 25V13h10v12M3 27h26M16 13v12" /></svg></span><div><span className="brand-name">校園 AI 平台客服</span><span className="brand-subtitle">CAMPUS SERVICE DESK</span></div></div><span className="demo-label">教學示範平台</span></header>
    <main className="workspace">
      <aside className="service-guide" aria-label="服務說明"><div><p className="section-label">服務指南 <span>／ 01</span></p><h2>平台使用<br />與問題排查</h2><p className="guide-intro">關於平台的使用問題，<br />從這裡開始。</p><ul className="service-list"><li>平台操作與政策<span>01</span></li><li>公開故障紀錄<span>02</span></li><li>請求次數試算<span>03</span></li><li>人工支援指引<span>04</span></li></ul></div><div className="guide-note"><span className="note-rule" /><h3>詢問之前</h3><p>請勿提供 API Key、密碼或個人資料。試算時，只需提供各期間的已用次數。</p><p>人工管道尚未配置；此處提供指引，不建立工單或完成真人交接。</p></div></aside>
      <section className="chat" aria-labelledby="chat-heading">
        <div className="toolbar"><h1 id="chat-heading">線上諮詢</h1><button className="reset-button" disabled={busy} onClick={reset}><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 10a8 8 0 1 1 1 7M4 4v6h6" /></svg>清除對話</button></div>
        {turns.length === 0 && <div className="welcome"><p className="section-label">有什麼可以幫上忙的？</p><h2>平台的事，<br />在這裡問。</h2><p className="welcome-description">查操作、找紀錄，或算一算剩餘次數。<br className="desktop-break" />直接輸入問題，也可以從下方開始。</p><div className="examples" aria-label="範例問題">{examples.map(([category, label, question]) => <button disabled={busy} key={category} onClick={() => chooseExample(question)}><span className="example-category">{category}</span><span className="example-question">{label}</span><Arrow diagonal /></button>)}</div></div>}
        <div className="conversation" aria-live="polite" aria-busy={busy}>{turns.map((turn, index) => <article className="turn" key={index}><div className="question"><span className="message-label">你</span><p>{turn.question}</p></div><div className="answer"><div className="answer-heading"><span className="answer-dot" aria-hidden="true" /><h2>平台客服</h2><span className="turn-number">{String(index + 1).padStart(2, '0')}</span></div><p className="reply">{turn.reply}</p><ToolTraces traces={turn.tool_traces} /></div></article>)}</div>
        {busy && <p className="busy-status" role="status"><span className="loading-dot" aria-hidden="true" />正在處理，請稍候…</p>}
        <form className="composer" onSubmit={send}><label htmlFor="message">你的問題</label><div className="input-shell"><textarea ref={inputRef} id="message" value={message} maxLength={4000} disabled={busy} onChange={event => setMessage(event.target.value)} aria-describedby={error ? "input-hint input-error" : "input-hint"} placeholder="例如：如何使用 OpenAI SDK 連接？" required/><div className="composer-actions"><span id="input-hint">可接續提問，保留本次對話脈絡</span><button className="send" disabled={busy || !message.trim()}><span>{busy ? '處理中' : '送出問題'}</span><Arrow /></button></div></div>{error && <p id="input-error" role="alert" className="error">{error}</p>}</form>
        <p className="data-note">本平台為虛構教學示範。政策、額度及故障紀錄皆為模擬資料，不代表真實學校或服務狀態。人工管道尚未配置，不建立工單或完成真人交接。請勿提供金鑰、密碼或個人資料。</p>
      </section>
    </main><footer className="site-footer"><span>Campus Service Desk</span><span>教學示範 · 模擬資料</span></footer>
  </>;
}

createRoot(document.getElementById('root')!).render(<App />);
