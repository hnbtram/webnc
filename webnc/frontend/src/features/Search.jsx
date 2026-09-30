import { useState } from 'react';
import { API_BASE, postImage, postJson } from '../api.js';

export default function Search() {
    const [query, setQuery] = useState('yellow sunflowers in a field');
    const [state, setState] = useState({ status: 'idle' });

    async function run(promise) {
        setState({ status: 'loading' });
        try {
            setState({ status: 'ok', results: (await promise).results });
        } catch (err) {
            setState({ status: 'error', error: err.message });
        }
    }

    function onPickImage(file) {
        if (!file) return;
        run(postImage('/api/search/image', file, { k: 12 }));
    }

    return (
        <section>
            <h2>Tìm kiếm ảnh bằng CLIP</h2>
            <p className="muted">
                Kho ảnh: COCO128 + một phần bộ Flowers. Câu mô tả dùng tiếng Anh.
            </p>

            <form
                className="search-bar"
                onSubmit={(e) => {
                    e.preventDefault();
                    run(postJson('/api/search/text', { query, k: 12 }));
                }}
            >
                <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="a dog on a sofa"
                    aria-label="Câu mô tả"
                />
                <button className="button" type="submit">
                    🔍 Tìm
                </button>

                <label className="button image-btn">
                    📁 Ảnh
                    <input
                        type="file"
                        accept="image/*"
                        hidden
                        onChange={(e) => {
                            onPickImage(e.target.files?.[0]);
                            e.target.value = '';
                        }}
                    />
                </label>
            </form>

            {state.status === 'loading' && <p className="muted">Đang tìm…</p>}
            {state.status === 'error' && <p className="error">{state.error}</p>}
            {state.status === 'ok' && (
                <div className="gallery">
                    {state.results.map((r) => (
                        <figure key={r.id}>
                            <img src={`${API_BASE}${r.url}`} alt={r.label} loading="lazy" />
                            <figcaption>
                                {r.label} · {r.score.toFixed(3)}
                            </figcaption>
                        </figure>
                    ))}
                </div>
            )}
        </section>
    );
}