import { useState } from 'react';
import './EventDecisionModal.css';

interface EventChoice {
    id: string;
    label: string;
    description: string;
    effects: Record<string, any>;
}

interface DecisionEvent {
    id: number;
    title: string;
    description: string;
    choices: EventChoice[];
    deadline_month: number;
    deadline_year: number;
}

interface Props {
    event: DecisionEvent;
    onDecide: (choiceId: string) => Promise<void>;
    onClose: () => void;
}

function formatEffect(key: string, value: any): string {
    if (typeof value === 'boolean') {
        return `${key.replace(/_/g, ' ')}: ${value ? 'Yes' : 'No'}`;
    }

    if (key === 'cash') {
        return `Cash: ${value >= 0 ? '+' : ''}$${value.toLocaleString()}`;
    }

    if (key.includes('modifier') || key.includes('risk') || key.includes('chance')) {
        const percent = (value * 100).toFixed(0);
        return `${key.replace(/_/g, ' ')}: ${percent}%`;
    }

    if (typeof value === 'number') {
        return `${key.replace(/_/g, ' ')}: ${value}`;
    }

    return `${key.replace(/_/g, ' ')}: ${value}`;
}

export function EventDecisionModal({ event, onDecide, onClose }: Props) {
    const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleDecide = async () => {
        if (!selectedChoice || isSubmitting) return;

        setIsSubmitting(true);
        try {
            await onDecide(selectedChoice);
        } catch (error) {
            console.error('Error making decision:', error);
            alert('Failed to submit decision. Please try again.');
            setIsSubmitting(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="event-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>⚡ {event.title}</h2>
                    <button className="close-btn" onClick={onClose}>×</button>
                </div>

                <p className="event-description">{event.description}</p>

                <div className="deadline">
                    ⏰ Decision Deadline: {event.deadline_month}/{event.deadline_year}
                </div>

                <div className="choices">
                    {event.choices.map((choice) => (
                        <div
                            key={choice.id}
                            className={`choice-card ${selectedChoice === choice.id ? 'selected' : ''}`}
                            onClick={() => setSelectedChoice(choice.id)}
                        >
                            <div className="choice-header">
                                <input
                                    type="radio"
                                    name="decision"
                                    checked={selectedChoice === choice.id}
                                    onChange={() => setSelectedChoice(choice.id)}
                                />
                                <h3>{choice.label}</h3>
                            </div>

                            <p className="choice-description">{choice.description}</p>

                            <div className="effects">
                                <strong>Effects:</strong>
                                {Object.entries(choice.effects).map(([key, value]) => (
                                    <span key={key} className={`effect-badge ${value < 0 || key.includes('risk') ? 'negative' : 'positive'}`}>
                                        {formatEffect(key, value)}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="modal-actions">
                    <button className="btn-cancel" onClick={onClose}>
                        Cancel
                    </button>
                    <button
                        className="btn-confirm"
                        onClick={handleDecide}
                        disabled={!selectedChoice || isSubmitting}
                    >
                        {isSubmitting ? 'Submitting...' : 'Confirm Decision'}
                    </button>
                </div>
            </div>
        </div>
    );
}
