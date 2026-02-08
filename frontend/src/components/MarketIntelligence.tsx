import { useState, useEffect } from 'react';
import type { Company } from '../types/index';
import { CompetitorCard } from './CompetitorCard';

const API_URL = 'http://localhost:8000';

export function MarketIntelligence() {
    const [companies, setCompanies] = useState<Company[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchGameState();
    }, []);

    const fetchGameState = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/game/state`);
            const data = await res.json();
            setCompanies(data.companies);
        } catch (err) {
            console.error("Error fetching market intel:", err);
        } finally {
            setLoading(false);
        }
    };

    const competitors = companies.filter(c => !c.is_player);

    if (loading) return <div>Data loading...</div>;

    return (
        <div className="market-intelligence-dashboard">
            <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2>🌍 Global Market Intelligence</h2>
                <button onClick={fetchGameState}>Refresh Intel</button>
            </div>

            <p style={{ color: '#aaa', marginBottom: '1rem' }}>
                Real-time analysis of competitor strategies, financial health, and AI decision patterns.
            </p>

            <div className="competitor-grid" style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: '1rem'
            }}>
                {competitors.map(comp => (
                    <CompetitorCard key={comp.id} company={comp} />
                ))}
            </div>

            {competitors.length === 0 && (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
                    No competitors found. Start a new game to generate AI opponents.
                </div>
            )}
        </div>
    );
}
