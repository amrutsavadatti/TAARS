import React from "react";

interface Props {
  questions: string[];
  onSelect: (q: string) => void;
}

export function SuggestedQuestions({ questions, onSelect }: Props) {
  if (questions.length === 0) return null;

  return (
    <div className="suggestions">
      <span className="suggestions-label">Try asking</span>
      {questions.map((q) => (
        <button
          key={q}
          className="suggestion-btn"
          onClick={() => onSelect(q)}
          type="button"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
