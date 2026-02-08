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
            // Sort companies: Player first, then by Brand Equity desc
            const sorted = data.companies.sort((a: Company, b: Company) => {
                if (a.is_player) return -1;
                if (b.is_player) return 1;
                return (b.brand_equity || 0) - (a.brand_equity || 0);
            });
            setCompanies(sorted);
        } catch (err) {
            console.error("Error fetching market intel:", err);
        } finally {
            setLoading(false);
        }
    };

    // No longer filtering out the player
    const displayedCompanies = companies;

    if (loading) return <div>Data loading...</div>;

    return (
        <div className="market-intelligence-dashboard">
            <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2>🌍 Global Market Intelligence</h2>
                <button onClick={fetchGameState}>Refresh Intel</button>
            </div>

            <p style={{ color: '#aaa', marginBottom: '1rem' }}>
                Real-time analysis of market presence, financial health, and competitor strategies.
            </p>

            <div className="competitor-grid" style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: '1rem'
            }}>
                {displayedCompanies.map(comp => (
                    <CompetitorCard key={comp.id} company={comp} />
                ))}
            </div>

            {displayedCompanies.length === 0 && (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
                    No companies found. Start a new game to generate the market.
                </div>
            )}
        </div>
    );
}
