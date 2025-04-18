const CACHE_NAME = 'sistema-representacao-v0.1';
const urlsToCache = [
    '/',
    '/static/logo.png',
    '/static/manifest.json',
    '/lista_pedidos',
    '/selecionar_empresa',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css'
];

self.addEventListener('install', event => {
    console.log('Service Worker: Instalando...');
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('Service Worker: Cache aberto, adicionando arquivos');
            return cache.addAll(urlsToCache);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    console.log('Service Worker: Ativando...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    console.log('Service Worker: Interceptando fetch para', url.pathname);

    // Ignorar solicitações não-GET e endpoints de sincronização
    if (event.request.method !== 'GET' || url.pathname === '/pedido' || url.pathname === '/consultar_cnpj' || url.pathname.startsWith('/buscar_catalogo')) {
        if (navigator.onLine) {
            console.log('Service Worker: Requisição dinâmica, buscando na rede:', url.pathname);
            event.respondWith(fetch(event.request));
        } else {
            console.log('Service Worker: Offline, ignorando requisição dinâmica:', url.pathname);
            event.respondWith(new Response('Offline', { status: 503 }));
        }
        return;
    }

    // Estratégia cache-first para recursos estáticos
    event.respondWith(
        caches.match(event.request).then(cachedResponse => {
            if (cachedResponse) {
                console.log('Service Worker: Retornando do cache:', url.pathname);
                return cachedResponse;
            }
            console.log('Service Worker: Buscando na rede:', url.pathname);
            return fetch(event.request).then(networkResponse => {
                if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
                    return networkResponse;
                }
                const responseToCache = networkResponse.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, responseToCache);
                });
                return networkResponse;
            }).catch(() => {
                console.log('Service Worker: Rede falhou, retornando offline.html para', url.pathname);
                return caches.match('/static/offline.html');
            });
        })
    );
});

async function renderListaPedidosOffline() {
    console.log('Iniciando renderização da página offline para /lista_pedidos');
    try {
        let pedidosPendentes = [];
        try {
            const request = indexedDB.open('SistemaDB', 2);
            const db = await new Promise((resolve, reject) => {
                request.onupgradeneeded = event => {
                    const db = event.target.result;
                    if (!db.objectStoreNames.contains('pendingRequests')) {
                        db.createObjectStore('pendingRequests', { keyPath: 'id' });
                    }
                    if (!db.objectStoreNames.contains('catalogo')) {
                        db.createObjectStore('catalogo', { keyPath: 'empresa' });
                    }
                    if (!db.objectStoreNames.contains('config')) {
                        db.createObjectStore('config', { keyPath: 'key' });
                    }
                };
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            const tx = db.transaction('pendingRequests', 'readonly');
            const store = tx.objectStore('pendingRequests');
            pedidosPendentes = await new Promise((resolve) => {
                const request = store.getAll();
                request.onsuccess = () => {
                    console.log('Pedidos pendentes recuperados do IndexedDB:', request.result);
                    resolve(request.result || []);
                };
                request.onerror = () => {
                    console.error('Erro ao executar getAll:', request.error);
                    resolve([]);
                };
            });
            await tx.complete;
            db.close();
            console.log('Total de pedidos pendentes:', pedidosPendentes.length);
        } catch (error) {
            console.error('Erro ao acessar pendingRequests:', error);
            pedidosPendentes = [];
        }

        let tabelaPedidos = '<tr><td colspan="4">Nenhum pedido pendente</td></tr>';
        if (pedidosPendentes.length > 0) {
            tabelaPedidos = '';
            for (let p of pedidosPendentes) {
                try {
                    const id = p.id || 'N/A';
                    const cnpj = p.data?.cnpj || 'N/A';
                    const razao = p.data?.razao || 'N/A';
                    const itensCount = p.data?.itens?.length || 0;
                    tabelaPedidos += `
                        <tr>
                            <td>${id}</td>
                            <td>${cnpj}</td>
                            <td>${razao}</td>
                            <td>${itensCount}</td>
                        </tr>`;
                } catch (err) {
                    console.error('Erro ao processar pedido:', p, err);
                }
            }
        } else {
            console.log('Nenhum pedido pendente encontrado para renderização');
        }

        const html = `
            <!DOCTYPE html>
            <html lang="pt-br">
            <head>
                <meta charset="UTF-8">
                <title>Pedidos - Sistema de Representação</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body { display: flex; min-height: 100vh; }
                    .sidebar { width: 250px; background-color: #343a40; color: white; position: fixed; height: 100%; }
                    .sidebar a { color: white; text-decoration: none; padding: 10px; display: block; }
                    .sidebar a:hover { background-color: #495057; }
                    .content { margin-left: 250px; padding: 20px; width: 100%; }
                    .navbar { background-color: #343a40; color: white; padding: 10px; }
                    .navbar img { height: 40px; }
                </style>
            </head>
            <body>
                <nav class="navbar">
                    <div class="container-fluid">
                        <a href="/" class="navbar-brand">
                            <img src="/static/logo.png" alt="Logo" class="d-inline-block align-text-top">
                        </a>
                        <div>
                            <span>Offline Mode</span>
                            <a href="/logout" class="btn btn-outline-light btn-sm ms-2" onclick="alert('Logout não disponível offline')">Logout</a>
                        </div>
                    </div>
                </nav>
                <div class="sidebar">
                    <h4 class="p-3">Menu</h4>
                    <a href="/lista_pedidos">Pedidos</a>
                    <a href="/" onclick="alert('Navegação limitada offline')">Início</a>
                </div>
                <div class="content">
                    <h1>Lista de Pedidos (Offline)</h1>
                    <div class="alert alert-warning">Modo Offline: Usando dados salvos localmente</div>
                    <p>Pedidos pendentes de sincronização:</p>
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>ID Local</th>
                                <th>CNPJ</th>
                                <th>Razão Social</th>
                                <th>Itens</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${tabelaPedidos}
                        </tbody>
                    </table>
                    <h2>Novo Pedido</h2>
                    <form id="novoPedidoForm" onsubmit="if(validarFormulario()) { salvarPedidoOffline(event); } return false;">
                        <div class="row mb-3">
                            <div class="col-md-4">
                                <label for="cnpj" class="form-label">CNPJ</label>
                                <input type="text" class="form-control form-control-sm" id="cnpj" name="cnpj" placeholder="Digite o CNPJ (consulta desativada offline)" required />
                            </div>
                            <div class="col-md-6">
                                <label for="razao" class="form-label">Razão Social</label>
                                <input type="text" class="form-control form-control-sm" id="razao" name="razao" required />
                            </div>
                        </div>
                        <div class="mb-3">
                            <button type="button" class="btn btn-success btn-sm" id="btnAdicionarItem">Adicionar Item</button>
                        </div>
                        <table class="table table-bordered" id="tabelaItens">
                            <thead>
                                <tr>
                                    <th>Código</th>
                                    <th>Descritivo</th>
                                    <th>Quantidades</th>
                                    <th>Vlr. Unit.</th>
                                    <th>Vlr. Total</th>
                                    <th>Ação</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                        <div class="row mb-3">
                            <div class="col-md-3">
                                <label for="forma_pagamento" class="form-label">Forma de Pagamento</label>
                                <select class="form-select form-select-sm" id="forma_pagamento" name="forma_pagamento" required>
                                    <option value="1">À Vista</option>
                                    <option value="2">Boleto</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label for="desconto" class="form-label">Desconto (%)</label>
                                <input type="number" class="form-control form-control-sm" id="desconto" name="desconto" min="0" max="100" step="0.01" value="0" oninput="atualizarTotalGeral()" />
                            </div>
                            <div class="col-md-3">
                                <label for="totalGeral" class="form-label">Total Geral (R$)</label>
                                <input type="text" class="form-control form-control-sm" id="totalGeral" readonly />
                            </div>
                            <div class="col-md-3">
                                <label for="totalLiquido" class="form-label">Total Líquido (R$)</label>
                                <input type="text" class="form-control form-control-sm" id="totalLiquido" readonly />
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary btn-sm">Criar Pedido</button>
                    </form>
                </div>
                <script>
                    var itemCount = 0;

                    function openDB() {
                        return new Promise(function(resolve, reject) {
                            var request = indexedDB.open('SistemaDB', 2);
                            request.onupgradeneeded = function(event) {
                                var db = event.target.result;
                                if (!db.objectStoreNames.contains('pendingRequests')) {
                                    db.createObjectStore('pendingRequests', { keyPath: 'id' });
                                }
                                if (!db.objectStoreNames.contains('catalogo')) {
                                    db.createObjectStore('catalogo', { keyPath: 'empresa' });
                                }
                                if (!db.objectStoreNames.contains('config')) {
                                    db.createObjectStore('config', { keyPath: 'key' });
                                }
                            };
                            request.onsuccess = function(event) {
                                resolve(event.target.result);
                            };
                            request.onerror = function(event) {
                                reject(event.target.error);
                            };
                        });
                    }

                    async function carregarCatalogoOffline() {
                        try {
                            var db = await openDB();
                            var tx = db.transaction('catalogo', 'readonly');
                            var store = tx.objectStore('catalogo');
                            var request = store.get('Empresa A');
                            return new Promise(function(resolve) {
                                request.onsuccess = function() {
                                    console.log('Catálogo retornado do IndexedDB:', request.result);
                                    resolve(request.result ? request.result.data : null);
                                };
                                request.onerror = function() {
                                    console.error('Erro ao buscar catálogo:', request.error);
                                    resolve(null);
                                };
                            });
                        } catch (error) {
                            console.error('Erro ao carregar catálogo offline:', error);
                            return null;
                        }
                    }

                    function adicionarItem() {
                        try {
                            var tbody = document.querySelector('#tabelaItens tbody');
                            var row = document.createElement('tr');
                            var index = itemCount;

                            var tdCodigo = document.createElement('td');
                            var inputCodigo = document.createElement('input');
                            inputCodigo.type = 'text';
                            inputCodigo.name = 'codigo[]';
                            inputCodigo.className = 'form-control form-control-sm';
                            inputCodigo.required = true;
                            inputCodigo.addEventListener('blur', function() {
                                buscarItem(inputCodigo, index);
                            });
                            tdCodigo.appendChild(inputCodigo);

                            var tdDescritivo = document.createElement('td');
                            var inputDescritivo = document.createElement('input');
                            inputDescritivo.type = 'text';
                            inputDescritivo.name = 'descritivo[]';
                            inputDescritivo.className = 'form-control form-control-sm';
                            inputDescritivo.readOnly = true;
                            tdDescritivo.appendChild(inputDescritivo);

                            var tdQuantidades = document.createElement('td');
                            tdQuantidades.id = 'quantidades-' + index;
                            tdQuantidades.className = 'd-flex flex-wrap gap-1';

                            var tdValorUnit = document.createElement('td');
                            var inputValorUnit = document.createElement('input');
                            inputValorUnit.type = 'text';
                            inputValorUnit.name = 'valor_unit[]';
                            inputValorUnit.className = 'form-control form-control-sm text-end';
                            inputValorUnit.readOnly = true;
                            tdValorUnit.appendChild(inputValorUnit);

                            var tdTotal = document.createElement('td');
                            var inputTotal = document.createElement('input');
                            inputTotal.type = 'text';
                            inputTotal.name = 'total[]';
                            inputTotal.className = 'form-control form-control-sm text-end';
                            inputTotal.readOnly = true;
                            tdTotal.appendChild(inputTotal);

                            var tdAcao = document.createElement('td');
                            var btnRemover = document.createElement('button');
                            btnRemover.type = 'button';
                            btnRemover.className = 'btn btn-danger btn-sm';
                            btnRemover.textContent = 'X';
                            btnRemover.addEventListener('click', function() {
                                removerItem(btnRemover);
                            });
                            tdAcao.appendChild(btnRemover);

                            row.appendChild(tdCodigo);
                            row.appendChild(tdDescritivo);
                            row.appendChild(tdQuantidades);
                            row.appendChild(tdValorUnit);
                            row.appendChild(tdTotal);
                            row.appendChild(tdAcao);

                            tbody.appendChild(row);
                            itemCount = itemCount + 1;
                        } catch (error) {
                            console.error('Erro ao adicionar item:', error);
                        }
                    }

                    async function buscarItem(input, index) {
                        try {
                            var codigo = input.value;
                            if (!codigo) return;
                            var catalogo = await carregarCatalogoOffline();
                            console.log('Catálogo carregado:', catalogo, 'Buscando código:', codigo);
                            if (catalogo && catalogo[codigo]) {
                                processarItem(catalogo[codigo], input, index);
                            } else {
                                console.warn('Item não encontrado no catálogo offline:', codigo);
                                alert('Item não encontrado no catálogo offline.');
                            }
                        } catch (error) {
                            console.error('Erro ao buscar item:', error);
                            alert('Erro ao buscar item offline: ' + error.message);
                        }
                    }

                    function processarItem(data, input, index) {
                        try {
                            var row = input.closest('tr');
                            var descritivoInput = row.querySelector('input[name="descritivo[]"]');
                            descritivoInput.value = data.descritivo || '';

                            var valorUnitInput = row.querySelector('input[name="valor_unit[]"]');
                            valorUnitInput.value = (data.valor || 0).toFixed(2);

                            var quantidadesCell = row.querySelector('#quantidades-' + index);
                            while (quantidadesCell.firstChild) {
                                quantidadesCell.removeChild(quantidadesCell.firstChild);
                            }

                            var tamanhos = data.tamanhos || [];
                            for (var i = 0; i < tamanhos.length; i++) {
                                var tam = tamanhos[i];
                                var div = document.createElement('div');
                                div.className = 'input-group input-group-sm';
                                div.style.width = '80px';

                                var span = document.createElement('span');
                                span.className = 'input-group-text';
                                span.style.width = '30px';
                                span.textContent añho = tam;
                                div.appendChild(span);

                                var inputQtd = document.createElement('input');
                                inputQtd.type = 'number';
                                inputQtd.name = 'qtd_' + index + '_' + tam;
                                inputQtd.className = 'form-control';
                                inputQtd.min = '0';
                                inputQtd.style.width = '50px';
                                inputQtd.addEventListener('input', function() {
                                    calcularTotal(inputQtd, index);
                                });
                                div.appendChild(inputQtd);

                                quantidadesCell.appendChild(div);
                            }
                        } catch (error) {
                            console.error('Erro ao processar item:', error);
                        }
                    }

                    function calcularTotal(input, index) {
                        try {
                            var row = input.closest('tr');
                            var valorUnit = parseFloat(row.querySelector('input[name="valor_unit[]"]').value) || 0;
                            var total = 0;
                            var qtdInputs = row.querySelectorAll('input[name^="qtd_' + index + '_"]');
                            for (var i = 0; i < qtdInputs.length; i++) {
                                var qtd = parseInt(qtdInputs[i].value) || 0;
                                total += qtd * valorUnit;
                            }
                            row.querySelector('input[name="total[]"]').value = total.toFixed(2);
                            atualizarTotalGeral();
                        } catch (error) {
                            console.error('Erro ao calcular total:', error);
                        }
                    }

                    function atualizarTotalGeral() {
                        try {
                            var totalGeral = 0;
                            var totalInputs = document.querySelectorAll('input[name="total[]"]');
                            for (var i = 0; i < totalInputs.length; i++) {
                                totalGeral += parseFloat(totalInputs[i].value) || 0;
                            }
                            var desconto = parseFloat(document.getElementById('desconto').value) || 0;
                            var descontoValor = totalGeral * (desconto / 100);
                            var totalLiquido = totalGeral - descontoValor;
                            document.getElementById('totalGeral').value = totalGeral.toFixed(2);
                            document.getElementById('totalLiquido').value = totalLiquido.toFixed(2);
                        } catch (error) {
                            console.error('Erro ao atualizar total geral:', error);
                        }
                    }

                    function removerItem(button) {
                        try {
                            button.closest('tr').remove();
                            atualizarTotalGeral();
                        } catch (error) {
                            console.error('Erro ao remover item:', error);
                        }
                    }

                    function validarFormulario() {
                        console.log('validarFormulario chamado');
                        try {
                            var rows = document.querySelectorAll('#tabelaItens tbody tr');
                            if (rows.length === 0) {
                                alert('Adicione pelo menos um item ao pedido.');
                                return false;
                            }
                            for (var i = 0; i < rows.length; i++) {
                                var row = rows[i];
                                var codigo = row.querySelector('input[name="codigo[]"]').value;
                                if (!codigo) {
                                    alert('Todos os itens devem ter um código válido.');
                                    return false;
                                }
                                var qtdInputs = row.querySelectorAll('input[name^="qtd_"]');
                                var hasQuantity = false;
                                for (var j = 0; j < qtdInputs.length; j++) {
                                    if (parseInt(qtdInputs[j].value) > 0) {
                                        hasQuantity = true;
                                        break;
                                    }
                                }
                                if (!hasQuantity) {
                                    alert('Cada item deve ter pelo menos uma quantidade maior que zero.');
                                    return false;
                                }
                            }
                            console.log('Formulário validado com sucesso');
                            return true;
                        } catch (error) {
                            console.error('Erro ao validar formulário:', error);
                            return false;
                        }
                    }

                    async function salvarPedidoOffline(event) {
                        event.preventDefault();
                        if (!validarFormulario()) {
                            return;
                        }
                        try {
                            var form = document.getElementById('novoPedidoForm');
                            var formData = new FormData(form);
                            var db = await openDB();
                            var pedido = {
                                id: Date.now(),
                                data: {
                                    cnpj: formData.get('cnpj'),
                                    razao: formData.get('razao'),
                                    forma_pagamento: formData.get('forma_pagamento'),
                                    desconto: formData.get('desconto'),
                                    itens: []
                                }
                            };
                            var rows = document.querySelectorAll('#tabelaItens tbody tr');
                            for (var i = 0; i < rows.length; i++) {
                                var row = rows[i];
                                var codigo = row.querySelector('input[name="codigo[]"]').value;
                                var quantidades = {};
                                var qtdInputs = row.querySelectorAll('input[name^="qtd_"]');
                                for (var j = 0; j < qtdInputs.length; j++) {
                                    var tam = qtdInputs[j].name.split('_')[2];
                                    quantidades[tam] = parseInt(qtdInputs[j].value) || 0;
                                }
                                if (codigo && Object.values(quantidades).some(function(q) { return q > 0; })) {
                                    pedido.data.itens.push({ codigo: codigo, quantidades: quantidades });
                                }
                            }
                            console.log('Salvando pedido no IndexedDB:', pedido);
                            var tx = db.transaction('pendingRequests', 'readwrite');
                            var store = tx.objectStore('pendingRequests');
                            await store.put(pedido);
                            await tx.complete;
                            alert('Pedido salvo localmente. Será sincronizado quando online.');
                            form.reset();
                            document.querySelector('#tabelaItens tbody').innerHTML = '';
                            location.reload();
                        } catch (error) {
                            console.error('Erro ao salvar pedido offline:', error);
                            alert('Erro ao salvar pedido offline: ' + error.message);
                        }
                    }

                    document.addEventListener('DOMContentLoaded', function() {
                        var btnAdicionar = document.getElementById('btnAdicionarItem');
                        if (btnAdicionar) {
                            btnAdicionar.addEventListener('click', function(event) {
                                event.preventDefault();
                                adicionarItem();
                            });
                        }
                    });
                </script>
            </body>
            </html>
        `;
        console.log('HTML offline gerado com sucesso');
        return new Response(html, {
            status: 200,
            headers: { 'Content-Type': 'text/html' }
        });
    } catch (error) {
        console.error('Erro ao renderizar página offline:', error);
        return new Response('Erro ao carregar pedidos offline: ' + error.message, {
            status: 500,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}