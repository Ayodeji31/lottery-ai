import React from "react";
import { motion } from "framer-motion";

const sizes = {
  sm: "h-9 w-9 text-sm",
  md: "h-12 w-12 text-lg",
  lg: "h-14 w-14 text-xl",
};

export const LotteryBall = ({ number, index = 0, bonus = false, size = "md", animate = true }) => {
  const gradient = bonus
    ? "from-amber-300 to-amber-600 shadow-[inset_-4px_-4px_10px_rgba(0,0,0,0.3),_0_6px_16px_rgba(251,191,36,0.35)]"
    : "from-sky-300 to-sky-600 shadow-[inset_-4px_-4px_10px_rgba(0,0,0,0.3),_0_6px_16px_rgba(14,165,233,0.35)]";
  const Comp = animate ? motion.div : "div";
  const animProps = animate
    ? {
        initial: { scale: 0, rotate: -90, opacity: 0 },
        animate: { scale: 1, rotate: 0, opacity: 1 },
        transition: { delay: index * 0.09, type: "spring", stiffness: 260, damping: 18 },
      }
    : {};
  return (
    <Comp
      {...animProps}
      data-testid={`lottery-ball-${bonus ? "bonus-" : ""}${number}`}
      className={`${sizes[size]} rounded-full bg-gradient-to-br ${gradient} flex items-center justify-center font-mono font-bold text-white select-none`}
    >
      {number}
    </Comp>
  );
};

export const BallRow = ({ main = [], bonus = [], size = "md", animate = true, label }) => (
  <div className="flex flex-wrap items-center gap-2">
    {main.map((n, i) => (
      <LotteryBall key={`m-${n}-${i}`} number={n} index={i} size={size} animate={animate} />
    ))}
    {bonus.length > 0 && (
      <>
        <span className="mx-1 text-muted-foreground font-mono text-sm">+</span>
        {bonus.map((n, i) => (
          <LotteryBall key={`b-${n}-${i}`} number={n} index={main.length + i} bonus size={size} animate={animate} />
        ))}
      </>
    )}
  </div>
);
