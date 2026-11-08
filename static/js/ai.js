/**
 * AI 终端模块 — 自然语言指令发送与结果渲染。
 * 挂载到 window.RF3D.ai。
 */
(function () {
    'use strict';
    window.RF3D = window.RF3D || {};

    const ai = {
        init: function () {
            const nlpButton = document.getElementById('nlp-button');
            const nlpInput = document.getElementById('nlp-input');
            if (!nlpButton || !nlpInput) return;

            nlpButton.addEventListener('click', async () => {
                const userInput = nlpInput.value.trim();

                if (!userInput) {
                    window.RF3D.showStatus('请输入打印需求', true);
                    return;
                }

                // 检查是否已加载模型
                if (!window.RF3D.viewer.hasModel()) {
                    window.RF3D.showStatus('请先上传并加载STL模型文件', true);
                    return;
                }

                nlpButton.disabled = true;
                nlpButton.textContent = '处理中...';

                try {
                    const response = await fetch('/ai-terminal', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ input: userInput })
                    });

                    if (!response.ok) {
                        throw new Error(`服务器错误: ${response.status}`);
                    }

                    const data = await response.json();
                    const aiResultEl = document.getElementById('ai-result');

                    if (data.status === 'success') {
                        const ops = data.operations || [];
                        const opDesc = ops.map((op, i) =>
                            `${i + 1}. ${op.description || op.command}`
                        ).join('  ');
                        // execution_results 是混合数组：load_model 返回裸字符串，
                        // 其余是 {command, status, result|error} 对象。
                        // 以前只保留 typeof === 'string'，等于把 slice / path / gcode 的
                        // 执行结果全部丢掉，用户永远只看到第一句「加载模型」。
                        const formatResult = (r) => {
                            if (typeof r === 'string') return r;
                            if (!r || typeof r !== 'object') return null;
                            const cmd = r.command || '操作';
                            if (r.status === 'error') {
                                return `${cmd}: 失败(${r.error || '未知错误'})`;
                            }
                            const detail = typeof r.result === 'string' ? r.result : '';
                            return detail ? `${cmd}: ${detail}` : `${cmd}: 完成`;
                        };
                        const execResults = (data.execution_results || [])
                            .map(formatResult)
                            .filter(Boolean)
                            .map(r => r.length > 60 ? r.substring(0, 60) + '…' : r)
                            .join(' | ');

                        if (aiResultEl) {
                            const line = document.createElement('div');
                            line.textContent = opDesc + (execResults ? '  →  ' + execResults : '');
                            line.style.cssText = 'font-size:0.78rem;color:#c0c0c0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
                            aiResultEl.replaceChildren(line);
                            aiResultEl.style.display = 'flex';
                        }
                    } else {
                        window.RF3D.showStatus('AI处理失败: ' + data.message, true);
                    }
                } catch (error) {
                    console.error('AI请求失败:', error);
                    window.RF3D.showStatus('请求失败: ' + error.message, true);
                } finally {
                    nlpButton.disabled = false;
                    nlpButton.textContent = '生成工艺方案';
                }
            });
        }
    };

    window.RF3D.ai = ai;
})();
