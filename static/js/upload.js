/**
 * 上传模块 — 拖拽/点击上传、文件类型校验、调用渲染模块加载模型。
 * 挂载到 window.RF3D.upload。
 */
(function () {
    'use strict';
    window.RF3D = window.RF3D || {};

    const upload = {
        dropzone: null,
        hiddenFileInput: null,
        uploadTrigger: null,
        modelContainer: null,

        init: function () {
            upload.dropzone = document.getElementById('dropzone');
            upload.hiddenFileInput = document.getElementById('hidden-file-input');
            upload.uploadTrigger = document.getElementById('upload-trigger');
            upload.modelContainer = document.getElementById('model-container');

            // 点击"点击上传"文本时，触发隐藏的文件选择框
            if (upload.uploadTrigger && upload.hiddenFileInput) {
                upload.uploadTrigger.addEventListener('click', () => {
                    upload.hiddenFileInput.click();
                });
            }

            // 当用户通过文件选择框选择文件后
            if (upload.hiddenFileInput) {
                upload.hiddenFileInput.addEventListener('change', (e) => {
                    if (e.target.files.length > 0) {
                        upload.handleFileUpload(e.target.files[0]);
                    }
                });
            }

            // 拖拽上传事件
            if (upload.dropzone) {
                upload.dropzone.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    upload.dropzone.style.borderColor = 'var(--accent-color)';
                });
                upload.dropzone.addEventListener('dragleave', () => {
                    upload.dropzone.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                });
                upload.dropzone.addEventListener('drop', (e) => {
                    e.preventDefault();
                    upload.dropzone.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                    if (e.dataTransfer.files.length > 0) {
                        upload.handleFileUpload(e.dataTransfer.files[0]);
                    }
                });
            }
        },

        // 处理文件上传的核心函数
        handleFileUpload: function (file) {
            console.log('正在处理文件:', file.name);

            // 简单的文件类型验证
            const allowedTypes = ['.stl', '.obj', '.3mf'];
            const fileExtension = file.name.toLowerCase().slice(-4);
            if (!allowedTypes.includes(fileExtension)) {
                window.RF3D.showStatus('请上传STL、OBJ或3MF格式的文件', true);
                return;
            }

            // 显示加载状态
            if (upload.dropzone) {
                upload.dropzone.innerHTML = '<i class="fas fa-spinner fa-spin"></i><p>正在上传并处理模型...</p>';
            }

            // 创建 FormData 对象来发送文件
            const formData = new FormData();
            formData.append('model_file', file);

            // 使用 fetch API 将文件发送到后端
            fetch('/upload-model', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`网络响应错误: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('后端响应:', data);

                if (data.status === 'success') {
                    // 隐藏上传区域，显示模型容器
                    if (upload.dropzone) {
                        upload.dropzone.style.display = 'none';
                    }
                    if (upload.modelContainer) {
                        upload.modelContainer.style.display = 'block';
                        upload.modelContainer.innerHTML = '';
                    }

                    // 确保 Three.js 场景已初始化
                    const viewer = window.RF3D.viewer;
                    if (!viewer.scene) {
                        viewer.initThree();
                    } else {
                        const container = document.getElementById('model-container');
                        if (container && viewer.renderer && !container.contains(viewer.renderer.domElement)) {
                            container.appendChild(viewer.renderer.domElement);
                        }
                    }

                    // 加载 3D 模型
                    viewer.loadModel(data.model_data);
                } else {
                    window.RF3D.showStatus('上传失败: ' + data.message, true);
                    upload.resetDropzone();
                }
            })
            .catch(error => {
                console.error('上传失败:', error);
                window.RF3D.showStatus('上传失败: ' + error.message, true);
                upload.resetDropzone();
            });
        },

        // 重置上传区域到初始状态
        resetDropzone: function () {
            if (!upload.dropzone) return;
            upload.dropzone.innerHTML = `
                <i class="fas fa-cloud-upload-alt upload-icon"></i>
                <p>拖放STL、OBJ或3MF文件到此处</p>
                <input type="file" id="hidden-file-input" style="display:none;" accept=".stl,.obj,.3mf">
                <p>或 <span style="color: var(--accent-color); cursor: pointer;" id="upload-trigger">点击上传</span></p>
            `;
            // 重新绑定：上传触发 → 隐藏文件框
            const trigger = document.getElementById('upload-trigger');
            const fileInput = document.getElementById('hidden-file-input');
            if (trigger && fileInput) {
                trigger.addEventListener('click', () => fileInput.click());
                fileInput.addEventListener('change', (e) => {
                    if (e.target.files.length > 0) upload.handleFileUpload(e.target.files[0]);
                });
            }
        }
    };

    window.RF3D.upload = upload;
})();
