import { useEffect, useState } from 'react';
import { getHealth } from './api.js';
import Classify from './features/Classify.jsx';
import Detect from './features/Detect.jsx';
import Search from './features/Search.jsx';
import Chat from './features/Chat.jsx';

const TABS = [
    { id: 'classify', label: 'Phân loại ảnh', icon: '🌼', model: 'classifier', Component: Classify },
    { id: 'detect', label: 'Phát hiện đối tượng', icon: '🚗', model: 'detector', Component: Detect },
    { id: 'search', label: 'Tìm kiếm ảnh', icon: '🔎', model: 'retrieval', Component: Search },
    { id: 'chat', label: 'Chatbot RAG', icon: '💬', model: 'llm', Component: Chat },
];

export default function App() {
    const [tab, setTab] = useState('classify');
    const [health, setHealth] = useState(null);

    useEffect(() => {
        getHealth().then(setHealth).catch(() => setHealth({ status: 'down', models: {} }));
    }, []);

    const current = TABS.find((t) => t.id === tab);
    const ready = health?.models?.[current.model];

    return (
        <div className="layout">
            {/* ============ SIDEBAR ============ */}
            <aside className="sidebar">
                <div className="brand">
                    <span className="brand-icon">🤖</span>
                    <div>
                        <h1>AI Web Apps</h1>
                        <p className={`status ${health?.status === 'ok' ? 'status-ok' : 'status-err'}`}>
                            {health
                                ? health.status === 'ok'
                                    ? `🟢 ${health.device.toUpperCase()}`
                                    : '🔴 Offline'
                                : '⏳ Đang kết nối…'}
                        </p>
                    </div>
                </div>

                <nav className="side-nav" role="tablist">
                    {TABS.map((t) => {
                        const enabled = health?.models?.[t.model];
                        return (
                            <button
                                key={t.id}
                                role="tab"
                                aria-selected={tab === t.id}
                                className={`side-tab ${tab === t.id ? 'active' : ''}`}
                                onClick={() => setTab(t.id)}
                            >
                                <span className="side-tab-icon">{t.icon}</span>
                                <span className="side-tab-label">{t.label}</span>
                                {health && !enabled && <span className="side-tab-badge">tắt</span>}
                            </button>
                        );
                    })}
                </nav>

                <footer className="sidebar-footer">
                    <p>© 2026 ShopLite Demo</p>
                </footer>
            </aside>

            {/* ============ MAIN ============ */}
            <main className="content">
                <div className="content-header">
                    <h2>
                        <span className="content-icon">{current.icon}</span>
                        {current.label}
                    </h2>
                    <p className="content-sub">
                        {health?.status === 'ok'
                            ? 'Backend đang hoạt động — sẵn sàng xử lý yêu cầu'
                            : 'Backend chưa kết nối'}
                    </p>
                </div>

                {health && !ready && (
                    <p className="error">
                        Mô hình “{current.model}” chưa được nạp ở backend.
                    </p>
                )}

                <div className="content-body">
                    <current.Component />
                </div>
            </main>
        </div>
    );
}