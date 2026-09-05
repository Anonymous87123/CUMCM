import type { DocumentHistory, HistoryDocumentSummary, HistoryRound } from "../types/app";

type Props = {
  currentDocId: string | null;
  currentHistory: DocumentHistory | null;
  items: HistoryDocumentSummary[];
  open: boolean;
  busy: boolean;
  onToggle: () => void;
  onSelect: (item: HistoryDocumentSummary) => void;
  onDelete: (docId: string, fromRound?: number) => void;
  onDownload: (item: HistoryRound, format: "txt" | "docx") => void;
};

function formatTimestamp(value: string): string {
  if (!value) {
    return "时间未知";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatDocName(item: HistoryDocumentSummary): string {
  const rawValue = item.originPath || item.sourcePath || item.docId;
  const parts = rawValue.split(/[\\/]/);
  return parts[parts.length - 1] || rawValue;
}

function formatNextRound(completedRounds: number[]): string {
  const filtered = completedRounds.filter((round) => round >= 1 && round <= 2);
  if (filtered.length >= 2) {
    return "已完成";
  }
  if (!filtered.length) {
    return "1";
  }
  return String(Math.max(...filtered) + 1);
}

export function HistoryCard({ currentDocId, currentHistory, items, open, busy, onToggle, onSelect, onDelete, onDownload }: Props) {
  return (
    <section className="glass-card section-stack history-card">
      <div className="section-header">
        <div>
          <h2>历史记录</h2>
          <p>显示已处理过的文档，可切换、回滚或删除。</p>
        </div>
        <button className="secondary-button history-toggle" onClick={onToggle} disabled={busy}>
          {open ? "收起历史记录" : `查看历史记录${items.length ? ` (${items.length})` : ""}`}
        </button>
      </div>
      {open ? (
        items.length ? (
          <div className="history-panel-scroll">
            <div className="history-list history-document-list">
              {items.map((item) => {
                const activeRounds = currentDocId === item.docId && currentHistory?.rounds.length ? currentHistory.rounds : item.rounds;
                const isActive = currentDocId === item.docId;
                return (
                  <article key={item.docId} className={`history-item history-document ${isActive ? "active" : ""}`}>
                    <div className="history-item-head history-document-head">
                      <div>
                        <strong>{formatDocName(item)}</strong>
                        <span>{item.lastTimestamp ? `最近更新 ${formatTimestamp(item.lastTimestamp)}` : "暂无时间"}</span>
                      </div>
                      <span className="pill">已完成 {item.completedRounds.length} 轮</span>
                    </div>
                    <div className="history-metrics">
                      <span>当前文档 {isActive ? "已载入" : "未载入"}</span>
                      <span>下一轮 {formatNextRound(item.completedRounds)}</span>
                    </div>
                    <div className="path-box compact-box">
                      <span>文档路径</span>
                      <strong>{item.originPath || item.sourcePath}</strong>
                    </div>
                    <div className="button-row history-document-actions">
                      <button className="secondary-button" onClick={() => onSelect(item)} disabled={busy}>
                        {isActive ? "重新载入" : "切换到此文档"}
                      </button>
                      <button className="secondary-button danger-button" onClick={() => onDelete(item.docId)} disabled={busy}>
                        删除整条历史
                      </button>
                    </div>
                    {activeRounds.length ? (
                      <div className="history-round-list">
                        {activeRounds.map((roundItem) => (
                          <article key={`${item.docId}-${roundItem.round}`} className="history-item history-round-item">
                            <div className="history-item-head">
                              <strong>第 {roundItem.round} 轮</strong>
                              <span>{formatTimestamp(roundItem.timestamp)}</span>
                            </div>
                            <div className="history-metrics">
                              <span>输入块数 {roundItem.inputSegmentCount ?? "-"}</span>
                              <span>输出块数 {roundItem.outputSegmentCount ?? "-"}</span>
                              <span>切块上限 {roundItem.chunkLimit ?? "-"}</span>
                            </div>
                            <div className="path-box compact-box">
                              <span>输出路径</span>
                              <strong>{roundItem.outputPath || "暂无"}</strong>
                            </div>
                            <div className="button-row">
                              <button
                                className="secondary-button"
                                onClick={() => onDownload(roundItem, "txt")}
                                disabled={busy || !roundItem.outputPath}
                              >
                                下载 TXT
                              </button>
                              <button
                                className="primary-button"
                                onClick={() => onDownload(roundItem, "docx")}
                                disabled={busy || !roundItem.outputPath}
                              >
                                下载 Word
                              </button>
                              <button
                                className="secondary-button danger-button"
                                onClick={() => onDelete(item.docId, roundItem.round)}
                                disabled={busy}
                              >
                                从本轮重新跑
                              </button>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="empty-state history-empty">
            <strong>还没有历史记录</strong>
            <p>执行过的文档会显示在这里，之后可以直接切换回来继续处理。</p>
          </div>
        )
      ) : (
        <div className="empty-state history-empty">
          <strong>历史记录已收起</strong>
          <p>点击右上角按钮查看之前处理过的文档和各轮输出。</p>
        </div>
      )}
    </section>
  );
}