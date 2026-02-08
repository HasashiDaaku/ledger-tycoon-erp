import React from 'react';
import type { Company } from '../types/index';

interface CompetitorCardProps {
    company: Company;
}

export const CompetitorCard: React.FC<CompetitorCardProps> = ({ company }) => {
    if (company.is_player) return null;

    const brandPercent = Math.min((company.brand_equity || 1.0) * 50, 100); // 1.0 = 50%, 2.0 = 100%
    const personalityColor = getPersonalityColor(company.personality || 'Unknown');

    // Count total stockouts
    const stockouts = company.strategy_memory?.stockouts
        ? Object.values(company.strategy_memory.stockouts).reduce((a, b) => a + b, 0)
        : 0;

    // Count total regret events
    const mistakes = company.strategy_memory?.pricing_regret
        ? Object.keys(company.strategy_memory.pricing_regret).length
        : 0;

    return (
        <div className="competitor-card" style={{
            border: `2px solid ${personalityColor}`,
            padding: '1rem',
            margin: '0.5rem',
            borderRadius: '8px',
            backgroundColor: '#1a1a1a'
        }}>
            <h3 style={{ borderBottom: `2px solid ${personalityColor}` }}>{company.name}</h3>

            <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <div className="stat-item">
                    <label>Strategy:</label>
                    <span style={{ color: personalityColor, fontWeight: 'bold' }}>
                        {company.personality || "Unknown"}
                    </span>
                </div>
                <div className="stat-item">
                    <label>Cash:</label>
                    <span>${company.cash?.toLocaleString() || "0"}</span>
                </div>
            </div>

            <div className="brand-section" style={{ marginTop: '0.5rem' }}>
                <label>Brand Presence:</label>
                <div className="progress-bar-bg" style={{ background: '#333', height: '10px', borderRadius: '5px', marginTop: '2px' }}>
                    <div
                        className="progress-bar-fill"
                        style={{
                            width: `${brandPercent}%`,
                            backgroundColor: personalityColor,
                            height: '100%',
                            borderRadius: '5px',
                            transition: 'width 0.5s ease'
                        }}
                    />
                </div>
                <small>{(company.brand_equity || 1.0).toFixed(2)}x Multiplier</small>
            </div>

            <div className="memory-section" style={{ marginTop: '1rem', borderTop: '1px solid #444', paddingTop: '0.5rem' }}>
                <h4>🧠 AI Memory</h4>
                <div className="memory-tags" style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                    {stockouts > 0 && (
                        <span className="tag" style={{ background: '#d32f2f', color: 'white', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>
                            ⚠️ {stockouts} Stockouts
                        </span>
                    )}
                    {mistakes > 0 && (
                        <span className="tag" style={{ background: '#f57c00', color: 'white', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>
                            📉 {mistakes} Pricing Errors
                        </span>
                    )}
                    {stockouts === 0 && mistakes === 0 && (
                        <span className="tag" style={{ background: '#388e3c', color: 'white', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>
                            ✅ Smooth Operations
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
};

function getPersonalityColor(personality: string): string {
    switch (personality.toLowerCase()) {
        case 'aggressive': return '#ff5252'; // Red
        case 'balanced': return '#448aff';   // Blue
        case 'premium': return '#ffd740';    // Gold
        case 'conservative': return '#69f0ae'; // Green
        default: return '#9e9e9e';           // Grey
    }
}
