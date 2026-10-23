import { useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Trace = { step: number; tool_name: string; arguments: unknown; result: unknown };
type Turn = { question: string; reply: string; tool_traces: Trace[] };

function App() {
  const [session, setSession] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
    } catch (cause) { setError(cause instanceof Error ? cause.message : '連線失敗'); }
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

  return <main>
    <header><span className="eyebrow">CAMPUS AI · SERVICE DESK</span><h1>校園 AI 平台客服</h1><p>虛構平台・教學示範資料，不代表真實學校政策或服務狀態。</p></header>
    <section className="workspace" aria-label="客服對話">
      <div className="chat">
        <div className="toolbar"><h2>資訊諮詢</h2><button disabled={busy} onClick={reset}>清除對話</button></div>
        {turns.length === 0 && <div className="welcome"><h3>想了解哪一項服務？</h3><p>可查操作指引、模擬政策與公開模擬故障，依你提供的用量試算剩餘請求次數，或取得人工支援指引。人工管道尚未配置，不建立工單或完成真人交接。請勿輸入金鑰或個人資料。</p><div className="examples">{['API Key 怎麼申請？', '429 代表什麼？', 'INC-001 處理到哪？', '假設每日20次，今天已用8次，還剩多少？', '一直無法登入，想找人工'].map(text => <button disabled={busy} key={text} onClick={() => setMessage(text)}>{text}</button>)}</div></div>}
        <div aria-live="polite">{turns.map((turn, index) => <article key={index}><p className="question">{turn.question}</p><p className="reply">{turn.reply}</p></article>)}</div>
        {error && <p role="alert" className="error">{error}</p>}
        <form onSubmit={send}><label htmlFor="message">你的問題</label><textarea id="message" value={message} maxLength={4000} disabled={busy} onChange={event => setMessage(event.target.value)} placeholder="例如：如何使用 OpenAI SDK 連接？" required/><button className="send" disabled={busy || !message.trim()}>{busy ? '處理中…' : '送出問題'}</button></form>
      </div>
      <aside><h2>工具執行軌跡</h2><p>顯示每輪實際工具名稱、參數與結果。</p>{turns.length === 0 && <p className="muted">送出問題後，軌跡會顯示於此。</p>}{turns.map((turn, index) => <section key={index}><h3>第 {index + 1} 輪</h3>{turn.tool_traces.length === 0 ? <p>本輪未執行工具</p> : turn.tool_traces.map((trace, i) => <details key={i} open><summary>{trace.tool_name} · 步驟 {trace.step}</summary><h4>參數</h4><pre>{JSON.stringify(trace.arguments, null, 2)}</pre><h4>結果</h4><pre>{JSON.stringify(trace.result, null, 2)}</pre></details>)}</section>)}</aside>
    </section>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
