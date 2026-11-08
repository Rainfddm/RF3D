/**
 * 切片模块 — 层滑块联动、切片参数收集、调用 /run-slice。
 * 挂载到 window.RF3D.slice。
 */
(function () {
    'use strict';
    window.RF3D = window.RF3D || {};

    const slice = {
        init: function () {
            // 层滑块事件监听
            const layerSlider = document.getElementById('layer-slider');
            const layerCountDisplay = document.getElementById('layer-count-display');
            if (layerSlider && layerCountDisplay) {
                layerSlider.addEventListener('input', function () {
                    const currentValue = this.value;
                    const maxValue = this.max;
                    layerCountDisplay.value = `${currentValue} / ${maxValue}`;
                });
            }

            // 切片按钮事件
            const sliceButton = document.getElementById('main-slice-btn');
            const statusDiv = document.getElementById('status');
            if (sliceButton) {
                sliceButton.addEventListener('click', async () => {
                    sliceButton.disabled = true;
                    if (statusDiv) {
                        statusDiv.textContent = "正在切片中，请稍候...";
                        statusDiv.style.color = "orange";
                    }

                    try {
                        // 只收集页面上真实存在、且用户确实填了值的输入。
                        // 以前这里给 8 个根本不存在的 id 兜了硬编码默认值
                        // （nozzle_diameter 0.4 / infill_density 50），而后端默认是
                        // nozzle_d 0.8 / infill_density 30 —— 前端每次切片都在覆盖后端默认值。
                        // 现在缺失的键直接不传，让 default_params 作为唯一真相源。
                        const slicingParams = {};
                        const putParam = (key, id, parse) => {
                            const el = document.getElementById(id);
                            if (!el) return;
                            const raw = (el.value ?? '').toString().trim();
                            if (raw === '') return;
                            const num = parse(raw);
                            if (Number.isFinite(num)) slicingParams[key] = num;
                        };
                        putParam('layer_height', 'layer-height', parseFloat);
                        putParam('first_layer_height', 'first-layer-height', parseFloat);
                        putParam('nozzle_diameter', 'nozzle-diameter', parseFloat);
                        putParam('filament_diameter', 'filament-diameter', parseFloat);
                        putParam('infill_density', 'infill-density', parseInt);
                        putParam('offset', 'offset', parseFloat);
                        putParam('extruder_temp', 'extruder-temp', parseInt);
                        putParam('bed_temp', 'bed-temp', parseInt);
                        putParam('speed', 'speed', parseInt);

                        // 发送 POST 请求到 /run-slice
                        const response = await fetch('/run-slice', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(slicingParams)
                        });

                        if (!response.ok) {
                            throw new Error(`服务器错误: ${response.status} ${response.statusText}`);
                        }

                        const data = await response.json();

                        if (data.status === 'success') {
                            window.RF3D.showStatus('切片成功！');
                        } else {
                            window.RF3D.showStatus('切片失败: ' + data.message, true);
                        }

                    } catch (error) {
                        console.error('切片请求失败:', error);
                        window.RF3D.showStatus('请求失败: ' + error.message, true);
                    } finally {
                        sliceButton.disabled = false;
                    }
                });
            }
        }
    };

    window.RF3D.slice = slice;
})();
