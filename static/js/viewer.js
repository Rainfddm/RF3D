/**
 * Three.js 渲染模块 — 场景 / 相机 / 渲染器 / 控制器 / 模型加载。
 * 挂载到 window.RF3D.viewer，供其他模块复用。
 */
(function () {
    'use strict';
    window.RF3D = window.RF3D || {};

    const viewer = {
        scene: null,
        camera: null,
        renderer: null,
        controls: null,
        animationId: null,

        animate: function () {
            viewer.animationId = requestAnimationFrame(viewer.animate);
            if (viewer.controls) viewer.controls.update();
            if (viewer.renderer && viewer.scene && viewer.camera) {
                viewer.renderer.render(viewer.scene, viewer.camera);
            }
        },

        // 初始化 Three.js 场景
        initThree: function () {
            if (typeof THREE === 'undefined') {
                console.error('THREE.js 未正确加载');
                return;
            }

            viewer.scene = new THREE.Scene();
            viewer.scene.background = new THREE.Color(0x1a1a1a);

            const container = document.getElementById('model-container');
            if (!container) return;

            viewer.camera = new THREE.PerspectiveCamera(75, container.offsetWidth / container.offsetHeight, 0.1, 10000);
            viewer.camera.position.z = 5;

            viewer.renderer = new THREE.WebGLRenderer({ antialias: true });
            viewer.renderer.setSize(container.offsetWidth, container.offsetHeight);
            viewer.renderer.shadowMap.enabled = true;
            container.appendChild(viewer.renderer.domElement);

            // 添加 OrbitControls
            viewer.controls = new THREE.OrbitControls(viewer.camera, viewer.renderer.domElement);
            viewer.controls.enableDamping = true;
            viewer.controls.dampingFactor = 0.05;

            // 添加光源
            const ambientLight = new THREE.AmbientLight(0x404040, 1.5);
            viewer.scene.add(ambientLight);

            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(1, 1, 1).normalize();
            directionalLight.castShadow = true;
            viewer.scene.add(directionalLight);

            const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight2.position.set(-1, -1, -1).normalize();
            viewer.scene.add(directionalLight2);

            // 添加坐标轴辅助线
            const axesHelper = new THREE.AxesHelper(5);
            viewer.scene.add(axesHelper);
        },

        // 加载模型数据
        loadModel: function (data) {
            try {
                // 清除场景中现有的模型
                if (viewer.scene) {
                    const objectsToRemove = [];
                    viewer.scene.traverse((child) => {
                        if (child.isMesh) {
                            objectsToRemove.push(child);
                        }
                    });
                    objectsToRemove.forEach((obj) => {
                        viewer.scene.remove(obj);
                    });
                }

                const geometry = new THREE.BufferGeometry();

                // 处理顶点数据
                if (!data || !data.vertices || !Array.isArray(data.vertices)) {
                    console.error('无效的顶点数据:', data);
                    return;
                }

                const vertices = new Float32Array(data.vertices.flat());
                geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));

                // 处理面片数据（三角形）
                const indices = [];
                if (!data || !data.faces || !Array.isArray(data.faces)) {
                    console.error('无效的面片数据:', data);
                    return;
                }

                data.faces.forEach(face => {
                    if (face.length === 3) {
                        indices.push(face[0], face[1], face[2]);
                    } else {
                        // 处理多边形面片（三角剖分）
                        for (let i = 1; i < face.length - 1; i++) {
                            indices.push(face[0], face[i], face[i + 1]);
                        }
                    }
                });
                geometry.setIndex(indices);

                // 计算法向量以获得更好的光照效果
                geometry.computeVertexNormals();

                // 创建材质和网格
                const material = new THREE.MeshPhongMaterial({
                    color: 0x00ff00,
                    specular: 0x111111,
                    shininess: 50,
                    side: THREE.DoubleSide,
                    transparent: true,
                    opacity: 0.9
                });
                const mesh = new THREE.Mesh(geometry, material);
                viewer.scene.add(mesh);

                // 自动调整相机视角
                const box = new THREE.Box3().setFromObject(mesh);
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                const fov = viewer.camera.fov * (Math.PI / 180);
                let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
                cameraZ *= 1.5; // 添加一些边距

                viewer.camera.position.set(center.x, center.y, cameraZ);
                viewer.camera.lookAt(center);

                // 更新控制器目标
                if (viewer.controls) {
                    viewer.controls.target.copy(center);
                    viewer.controls.update();
                }

                // 强制渲染场景
                viewer.renderer.render(viewer.scene, viewer.camera);
                console.log('模型加载完成');

                // 确保动画循环在运行
                if (!viewer.animationId) {
                    viewer.animate();
                }
            } catch (error) {
                console.error('加载模型时出错:', error);
                window.RF3D.showStatus('模型加载失败: ' + error.message, true);
            }
        },

        // 是否已加载模型
        hasModel: function () {
            return !!viewer.scene && viewer.scene.children.filter(c => c.isMesh).length > 0;
        }
    };

    // 窗口大小变化时更新渲染器和相机
    window.addEventListener('resize', function () {
        if (viewer.camera && viewer.renderer) {
            const container = document.getElementById('model-container');
            if (container) {
                viewer.camera.aspect = container.offsetWidth / container.offsetHeight;
                viewer.camera.updateProjectionMatrix();
                viewer.renderer.setSize(container.offsetWidth, container.offsetHeight);
            }
        }
    });

    window.RF3D.viewer = viewer;
})();
