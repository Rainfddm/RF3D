/**
 * 入口模块 — RF3D 命名空间、公共状态提示、模块初始化、UI 交互。
 * 挂载到 window.RF3D。
 */
(function () {
    'use strict';
    window.RF3D = window.RF3D || {};

    // 公共状态提示（供各模块调用）
    window.RF3D.showStatus = function (msg, isError) {
        const statusDiv = document.getElementById('status');
        if (statusDiv) {
            statusDiv.textContent = msg;
            statusDiv.style.color = isError ? '#e74c3c' : '#27ae60';
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        // 初始化各功能模块
        window.RF3D.upload.init();
        window.RF3D.ai.init();
        window.RF3D.slice.init();
        initUiInteractions();
    });

    function initUiInteractions() {
        // 面板标签切换
        const tabs = document.querySelectorAll('.panel-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', function () {
                tabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
            });
        });

        // 快速选择建议点击事件
        const nlpInput = document.getElementById('nlp-input');
        const nlpSuggestions = document.querySelectorAll('.suggestion');
        if (nlpSuggestions.length > 0 && nlpInput) {
            nlpSuggestions.forEach(suggestion => {
                suggestion.addEventListener('click', () => {
                    const currentText = nlpInput.value;
                    const suggestionText = suggestion.textContent;
                    if (currentText.trim() === '') {
                        nlpInput.value = suggestionText;
                    } else {
                        nlpInput.value = currentText + ' ' + suggestionText;
                    }
                    nlpInput.focus();
                });
            });
        }

        // 面板折叠功能
        const togglePanelBtn = document.getElementById('toggle-panel');
        const rightPanel = document.getElementById('right-panel');
        let isPanelCollapsed = false;

        if (togglePanelBtn && rightPanel) {
            togglePanelBtn.addEventListener('click', function () {
                isPanelCollapsed = !isPanelCollapsed;

                if (isPanelCollapsed) {
                    rightPanel.style.transform = 'translateX(100%)';
                    rightPanel.setAttribute('aria-hidden', 'true');
                    this.innerHTML = '<i class="fas fa-chevron-left"></i>';
                } else {
                    rightPanel.style.transform = 'translateX(0)';
                    rightPanel.setAttribute('aria-hidden', 'false');
                    this.innerHTML = '<i class="fas fa-chevron-right"></i>';
                }
            });
        }

        // 移动端响应式按钮
        const viewport = document.querySelector('.viewport');
        let panelToggleBtn = document.getElementById('mobile-panel-toggle');
        let nlpToggleBtn = document.getElementById('mobile-nlp-toggle');
        let toolbarToggleBtn = document.getElementById('mobile-toolbar-toggle');

        if (!panelToggleBtn) {
            panelToggleBtn = document.createElement('button');
            panelToggleBtn.className = 'mobile-panel-toggle';
            panelToggleBtn.id = 'mobile-panel-toggle';
            panelToggleBtn.innerHTML = '<i class="fas fa-cog"></i>';
            viewport.appendChild(panelToggleBtn);
        }

        if (!nlpToggleBtn) {
            nlpToggleBtn = document.createElement('button');
            nlpToggleBtn.className = 'mobile-nlp-toggle';
            nlpToggleBtn.id = 'mobile-nlp-toggle';
            nlpToggleBtn.innerHTML = '<i class="fas fa-comment"></i>';
            viewport.appendChild(nlpToggleBtn);
        }

        if (!toolbarToggleBtn) {
            toolbarToggleBtn = document.createElement('button');
            toolbarToggleBtn.className = 'mobile-toolbar-toggle';
            toolbarToggleBtn.id = 'mobile-toolbar-toggle';
            toolbarToggleBtn.innerHTML = '<i class="fas fa-bars"></i>';
            viewport.appendChild(toolbarToggleBtn);
        }

        // 检测是否为竖屏模式
        function isPortraitMode() {
            return window.innerHeight > window.innerWidth ||
                   (screen.orientation && screen.orientation.angle % 180 !== 0) ||
                   window.matchMedia("(orientation: portrait)").matches;
        }

        // 控制移动端按钮的显示
        function controlMobileButtonVisibility() {
            const isPortrait = isPortraitMode();
            const isSmallScreen = window.innerWidth <= 768;

            if (isSmallScreen && isPortrait) {
                panelToggleBtn.style.display = 'block';
                nlpToggleBtn.style.display = 'block';
                toolbarToggleBtn.style.display = 'block';

                if (rightPanel.getAttribute('aria-hidden') === 'true') {
                    panelToggleBtn.style.visibility = 'visible';
                } else {
                    panelToggleBtn.style.visibility = 'hidden';
                }

                const isNlpVisible = document.getElementById('nlp-panel').classList.contains('mobile-panel-visible');
                nlpToggleBtn.style.visibility = isNlpVisible ? 'hidden' : 'visible';

                const isToolbarVisible = document.getElementById('toolbar').classList.contains('mobile-toolbar-visible');
                toolbarToggleBtn.style.visibility = isToolbarVisible ? 'hidden' : 'visible';
            } else {
                panelToggleBtn.style.display = 'none';
                nlpToggleBtn.style.display = 'none';
                toolbarToggleBtn.style.display = 'none';
            }
        }

        window.addEventListener('resize', controlMobileButtonVisibility);

        if (screen.orientation) {
            screen.orientation.addEventListener('change', controlMobileButtonVisibility);
        } else {
            window.addEventListener('orientationchange', controlMobileButtonVisibility);
        }

        controlMobileButtonVisibility();

        const observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'aria-hidden') {
                    const isPortrait = isPortraitMode();
                    const isSmallScreen = window.innerWidth <= 768;

                    if (isSmallScreen && isPortrait) {
                        const isHidden = rightPanel.getAttribute('aria-hidden') === 'true';
                        panelToggleBtn.style.visibility = isHidden ? 'visible' : 'hidden';
                    }
                }
            });
        });

        observer.observe(rightPanel, {
            attributes: true
        });

        function toggleMobilePanel() {
            isPanelCollapsed = !isPanelCollapsed;

            if (isPanelCollapsed) {
                rightPanel.style.transform = 'translateX(100%)';
                rightPanel.setAttribute('aria-hidden', 'true');
                document.querySelector('#toggle-panel i').className = 'fas fa-chevron-left';
            } else {
                rightPanel.style.transform = 'translateX(0)';
                rightPanel.setAttribute('aria-hidden', 'false');
                document.querySelector('#toggle-panel i').className = 'fas fa-chevron-right';
            }
        }

        panelToggleBtn.addEventListener('click', function () {
            rightPanel.style.transform = 'translateX(0)';
            rightPanel.setAttribute('aria-hidden', 'false');
            document.querySelector('#toggle-panel i').className = 'fas fa-chevron-right';
            this.style.visibility = 'hidden';
        });

        nlpToggleBtn.addEventListener('click', function () {
            const nlpPanel = document.getElementById('nlp-panel');
            nlpPanel.classList.add('mobile-panel-visible');
            this.style.visibility = 'hidden';
        });

        toolbarToggleBtn.addEventListener('click', function () {
            const toolbar = document.getElementById('toolbar');
            toolbar.classList.add('mobile-toolbar-visible');
            this.style.visibility = 'hidden';
        });

        document.addEventListener('click', function (event) {
            const nlpPanel = document.getElementById('nlp-panel');
            const toolbar = document.getElementById('toolbar');
            const isClickInsideNlpPanel = nlpPanel.contains(event.target);
            const isClickOnNlpToggleBtn = nlpToggleBtn.contains(event.target);
            const isClickInsideToolbar = toolbar.contains(event.target);
            const isClickOnToolbarToggleBtn = toolbarToggleBtn.contains(event.target);

            if (!isClickInsideNlpPanel && !isClickOnNlpToggleBtn && isPortraitMode() && window.innerWidth <= 768) {
                nlpPanel.classList.remove('mobile-panel-visible');
                if (!rightPanel.classList.contains('mobile-panel-visible')) {
                    nlpToggleBtn.style.visibility = 'visible';
                }
            }

            if (!isClickInsideToolbar && !isClickOnToolbarToggleBtn && isPortraitMode() && window.innerWidth <= 768) {
                toolbar.classList.remove('mobile-toolbar-visible');
                if (!rightPanel.classList.contains('mobile-panel-visible') &&
                    !document.getElementById('nlp-panel').classList.contains('mobile-panel-visible')) {
                    toolbarToggleBtn.style.visibility = 'visible';
                }
            }
        });
    }
})();
