import React from 'react';

export default function Stepper({ steps, current, onSelect }) {
    return (
        <ul className="stepper">
            {steps.map((step, index) => (
                <li
                    key={index}
                    className={`step-item ${index === current ? 'active' : ''}`}
                    onClick={() => onSelect(index)}
                >
                    {index + 1}. {step}
                </li>
            ))}
        </ul>
    );
}