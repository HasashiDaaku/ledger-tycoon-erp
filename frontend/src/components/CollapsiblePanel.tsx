import React, { useState } from 'react';

interface CollapsiblePanelProps {
    title: string;
    children: React.ReactNode;
    defaultExpanded?: boolean;
    summary?: React.ReactNode;
}

export const CollapsiblePanel: React.FC<CollapsiblePanelProps> = ({
    title,
    children,
    defaultExpanded = false,
    summary
}) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    const toggle = () => setIsExpanded(!isExpanded);

    return (
        <div className={`panel collapsible-panel ${isExpanded ? 'expanded' : 'collapsed'}`}>
            <div className="panel-header" onClick={toggle}>
                <div className="header-content">
                    <h2>{title}</h2>
                    {summary && !isExpanded && (
                        <div className="panel-summary fade-in">
                            {summary}
                        </div>
                    )}
                </div>
                <button className="toggle-btn" aria-label={isExpanded ? "Collapse" : "Expand"}>
                    {isExpanded ? '▼' : '▶'}
                </button>
            </div>
            {isExpanded && (
                <div className="panel-content">
                    {children}
                </div>
            )}
        </div>
    );
};
