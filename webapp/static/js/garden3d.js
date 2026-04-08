// Конфигурация анимаций сада
const GARDEN_ANIMATIONS = {
    watering: {
        duration: 2000, // мс
        particleCount: 30,
        particleLifetime: 120, // кадров
        growthScale: 1.15,
        growthDuration: 60 // кадров
    },
    treeRotation: {
        speed: 0.1 // радиан/сек
    },
    particleRotation: {
        speed: 0.2 // радиан/сек
    }
};

const GARDEN_COLORS = {
    neon: {
        green: 0x4caf50,
        blue: 0x4facfe,
        yellow: 0xffc107,
        red: 0xff5555,
        cyan: 0x00f2fe
    },
    tree: {
        healthy: 0x3dcc6b,
        medium: 0x4facfe,
        low: 0xe0a800,
        withered: 0xa94442
    }
};

class Garden3D {
    constructor(canvas) {
        this.canvas = canvas;
        this.treeMeshes = [];
        this.selectionHandler = null;
        this.selectedMesh = null;
        this.raycaster = new THREE.Raycaster();
        this.pointer = new THREE.Vector2();
        if (!canvas || typeof THREE === 'undefined') {
            console.warn('[Garden3D] Canvas або Three.js недоступні');
            return;
        }

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0b112b);

        const width = canvas.clientWidth;
        const height = canvas.clientHeight;

        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        this.camera.position.set(10, 12, 16);
        this.camera.lookAt(0, 0, 0);

        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        this.renderer.setPixelRatio(window.devicePixelRatio || 1);
        this.renderer.setSize(width, height);

        // Улучшенное освещение
        const ambient = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambient);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(10, 15, 5);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.width = 2048;
        dirLight.shadow.mapSize.height = 2048;
        dirLight.shadow.camera.near = 0.5;
        dirLight.shadow.camera.far = 50;
        dirLight.shadow.camera.left = -20;
        dirLight.shadow.camera.right = 20;
        dirLight.shadow.camera.top = 20;
        dirLight.shadow.camera.bottom = -20;
        this.scene.add(dirLight);

        // Дополнительный неоновый свет для атмосферы
        const neonLight = new THREE.PointLight(0x4caf50, 0.5, 30);
        neonLight.position.set(0, 5, 0);
        this.scene.add(neonLight);

        // Включаем тени в рендерере
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        const groundGeo = new THREE.PlaneGeometry(80, 80);
        const groundMat = new THREE.MeshStandardMaterial({
            color: 0x0f1b3d,
            roughness: 0.9,
            metalness: 0.1
        });
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        this.scene.add(ground);

        this.clock = new THREE.Clock();
        this.animate = this.animate.bind(this);
        this.onPointerDown = this.onPointerDown.bind(this);
        this.canvas.addEventListener('pointerdown', this.onPointerDown);
        requestAnimationFrame(this.animate);
    }

    setSelectionHandler(handler) {
        this.selectionHandler = handler;
    }

    onPointerDown(event) {
        if (!this.scene || !this.camera || !this.treeMeshes.length) return;
        const rect = this.canvas.getBoundingClientRect();
        this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        this.raycaster.setFromCamera(this.pointer, this.camera);

        const allObjects = [];
        this.treeMeshes.forEach(group => {
            group.traverse(obj => {
                allObjects.push(obj);
            });
        });

        const intersects = this.raycaster.intersectObjects(allObjects, true);
        if (intersects.length === 0) {
            this.clearSelection();
            return;
        }
        const mesh = this.findTreeGroup(intersects[0].object);
        if (mesh) {
            this.selectMesh(mesh);
        } else {
            this.clearSelection();
        }
    }

    findTreeGroup(object) {
        let current = object;
        while (current && current.parent) {
            if (this.treeMeshes.includes(current)) {
                return current;
            }
            current = current.parent;
        }
        return null;
    }

    selectMesh(mesh) {
        if (this.selectedMesh === mesh) return;
        if (this.selectedMesh) {
            this.selectedMesh.scale.set(1, 1, 1);
        }
        this.selectedMesh = mesh;
        mesh.scale.set(1.1, 1.1, 1.1);
        if (this.selectionHandler) {
            this.selectionHandler(mesh.userData.meta || null);
        }
    }

    clearSelection() {
        if (this.selectedMesh) {
            this.selectedMesh.scale.set(1, 1, 1);
            this.selectedMesh = null;
        }
        if (this.selectionHandler) {
            this.selectionHandler(null);
        }
    }

    onResize() {
        if (!this.renderer || !this.camera || !this.canvas) return;
        const width = this.canvas.clientWidth;
        const height = this.canvas.clientHeight;
        if (height === 0) return;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    setTrees(trees = []) {
        if (!this.scene) return;
        this.clearTrees();

        const instances = [];
        let slotIndex = 0;
        trees.forEach(tree => {
            const count = tree.count || 1;
            for (let i = 0; i < count; i++) {
                instances.push({
                    type: tree.tree_type || 'tree',
                    watering: tree.watering_status || {},
                    slotKey: `${tree.tree_type || 'tree'}_${slotIndex}`,
                    slotIndex
                });
                slotIndex += 1;
            }
        });

        if (instances.length === 0) {
            return;
        }

        const grid = Math.ceil(Math.sqrt(instances.length));
        const spacing = 2.8;

        instances.forEach((tree, index) => {
            const mesh = this.createTreeMesh(tree);
            const col = index % grid;
            const row = Math.floor(index / grid);
            const offset = (grid - 1) * spacing * 0.5;
            mesh.position.set(col * spacing - offset, 0, row * spacing - offset);
            this.scene.add(mesh);
            this.treeMeshes.push(mesh);
        });
    }

    createTreeMesh(tree) {
        const group = new THREE.Group();
        const watering = tree.watering || {};

        // Улучшенный ствол с более детальной геометрией
        const trunkGeo = new THREE.CylinderGeometry(0.2, 0.28, 1.6, 12);
        const trunkMat = new THREE.MeshStandardMaterial({ 
            color: 0x5b3a29,
            roughness: 0.8,
            metalness: 0.1
        });
        const trunk = new THREE.Mesh(trunkGeo, trunkMat);
        trunk.position.y = 0.8;
        trunk.castShadow = true;
        trunk.receiveShadow = true;
        group.add(trunk);

        // Улучшенная крона - несколько слоев для более реалистичного вида
        const crownColor = this.getCrownColor(watering);
        const emissiveColor = this.getEmissiveColor(watering);
        const emissiveIntensity = watering.is_withered ? 0.1 : 0.3;

        // Основная крона
        const crownGeo = new THREE.ConeGeometry(1.0, 2.2, 16);
        const crownMat = new THREE.MeshStandardMaterial({
            color: crownColor,
            emissive: emissiveColor,
            emissiveIntensity: emissiveIntensity,
            roughness: 0.6,
            metalness: 0.0
        });
        const crown = new THREE.Mesh(crownGeo, crownMat);
        crown.position.y = 2.4;
        crown.castShadow = true;
        group.add(crown);

        // Верхний слой кроны для объема
        const topCrownGeo = new THREE.ConeGeometry(0.6, 1.2, 12);
        const topCrownMat = new THREE.MeshStandardMaterial({
            color: crownColor,
            emissive: emissiveColor,
            emissiveIntensity: emissiveIntensity * 1.2,
            roughness: 0.5
        });
        const topCrown = new THREE.Mesh(topCrownGeo, topCrownMat);
        topCrown.position.y = 3.2;
        topCrown.castShadow = true;
        group.add(topCrown);

        // Неоновое кольцо для индикации состояния
        const ringGeo = new THREE.TorusGeometry(1.4, 0.06, 8, 32);
        const ringColor = this.getRingColor(watering);
        const ringMat = new THREE.MeshBasicMaterial({
            color: ringColor,
            opacity: watering.is_withered ? 0.2 : 0.4,
            transparent: true
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 0.1;
        group.add(ring);

        // Частицы для здоровых деревьев
        if (!watering.is_withered && (watering.water_level || 100) > 60) {
            const particleCount = 8;
            const particles = new THREE.BufferGeometry();
            const positions = new Float32Array(particleCount * 3);
            for (let i = 0; i < particleCount; i++) {
                const angle = (i / particleCount) * Math.PI * 2;
                const radius = 1.5 + Math.random() * 0.3;
                positions[i * 3] = Math.cos(angle) * radius;
                positions[i * 3 + 1] = 2.0 + Math.random() * 1.5;
                positions[i * 3 + 2] = Math.sin(angle) * radius;
            }
            particles.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            const particleMat = new THREE.PointsMaterial({
                color: GARDEN_COLORS.neon.green,
                size: 0.15,
                transparent: true,
                opacity: 0.6
            });
            const particleSystem = new THREE.Points(particles, particleMat);
            group.add(particleSystem);
            group.userData.particles = particleSystem;
        }

        group.userData = {
            meta: {
                type: tree.type,
                slotKey: tree.slotKey,
                index: tree.slotIndex,
                isWithered: watering.is_withered,
                waterLevel: watering.water_level || 100,
                needsWater: (watering.water_level || 100) < 60,
                nextWaterSeconds: Math.max(0, watering.seconds_until_next_water || 0),
                canWater: watering.can_water_now !== false
            }
        };

        return group;
    }

    getCrownColor(watering) {
        if (!watering) return GARDEN_COLORS.tree.healthy;
        if (watering.is_withered) return GARDEN_COLORS.tree.withered;
        const level = watering.water_level || 100;
        if (level < 40) return GARDEN_COLORS.tree.low;
        if (level < 70) return GARDEN_COLORS.tree.medium;
        return GARDEN_COLORS.tree.healthy;
    }

    getEmissiveColor(watering) {
        if (!watering) return 0x001a0a;
        if (watering.is_withered) return 0x330000;
        const level = watering.water_level || 100;
        if (level < 40) return 0x332100;
        if (level < 70) return 0x002233;
        return 0x001a0a;
    }

    getRingColor(watering) {
        if (!watering) return GARDEN_COLORS.neon.green;
        if (watering.is_withered) return GARDEN_COLORS.neon.red;
        const level = watering.water_level || 100;
        if (level < 40) return GARDEN_COLORS.neon.yellow;
        if (level < 70) return GARDEN_COLORS.neon.blue;
        return GARDEN_COLORS.neon.green;
    }

    clearTrees() {
        if (!this.scene || !this.treeMeshes) return;
        this.clearSelection();
        this.treeMeshes.forEach(mesh => {
            this.scene.remove(mesh);
            mesh.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) {
                        obj.material.forEach(mat => mat.dispose && mat.dispose());
                    } else if (obj.material.dispose) {
                        obj.material.dispose();
                    }
                }
            });
        });
        this.treeMeshes = [];
    }

    animate() {
        if (this.renderer && this.scene && this.camera) {
            const delta = this.clock.getDelta();
            this.treeMeshes.forEach(mesh => {
                mesh.rotation.y += delta * GARDEN_ANIMATIONS.treeRotation.speed;
                // Анимация частиц
                if (mesh.userData.particles) {
                    mesh.userData.particles.rotation.y += delta * GARDEN_ANIMATIONS.particleRotation.speed;
                }
            });
            this.renderer.render(this.scene, this.camera);
        }
        requestAnimationFrame(this.animate);
    }
}

