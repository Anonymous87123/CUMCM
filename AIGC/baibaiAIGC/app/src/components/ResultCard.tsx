import type { RoundResult } from "../types/app";

type Props = {
  result: RoundResult | null;
  previewText: string;
  busy: boolean;
  onExportTxt: () => void;
  onExportDocx: () => void;
};

export function ResultCard({ result, previewText, busy, onExportTxt, onExportDocx }: Props) {
  return (
    <section className="glass-card section-stack result-card">
      <div className="section-header">
        <div>
          <h2>本轮结果</h2>
          <p>每轮结束后可直接预览，并选择导出为 txt 或 Word。</p>
        </div>
        {result ? <span className="pill">第 {result.round} 轮已完成</span> : null}
      </div>
      {result ? (
        <>
          <div className="info-grid compact">
            <div className="info-item">
              <span>切块上限</span>
              <strong>{result.chunkLimit}</strong>
            </div>
            <div className="info-item">
              <span>输入块数</span>
              <strong>{result.inputSegmentCount}</strong>
            </div>
            <div className="info-item">
              <span>输出块数</span>
              <strong>{result.outputSegmentCount}</strong>
            </div>
            <div className="info-item">
              <span>段落数</span>
              <strong>{result.paragraphCount}</strong>
            </div>
          </div>
          <div className="preview-box">
            <pre>{previewText || "当前轮次已完成，但还未读取预览。"}</pre>
          </div>
          <div className="button-row">
            <button className="secondary-button" onClick={onExportTxt} disabled={busy}>
              导出 TXT
            </button>
            <button className="primary-button" onClick={onExportDocx} disabled={busy}>
              导出 Word
            </button>
          </div>
        </>
      ) : (
        <div className="empty-state">
          <strong>结果区待生成</strong>
          <p>执行一轮处理后，这里会显示输出摘要和文本预览。</p>
        </div>
      )}
    </section>
  );
}
