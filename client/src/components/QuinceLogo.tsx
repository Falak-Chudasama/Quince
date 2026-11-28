import React from 'react'

interface QuinceLogoProps {
  size?: 'xs' | 'sm' | 'md' | 'lg'
  breathing?: boolean
  className?: string
}

const SIZE_MAP = {
  xs: 'h-4 w-4',
  sm: 'h-5 w-5',
  md: 'h-7 w-7',
  lg: 'h-12 w-12',
}

export const QuinceLogo: React.FC<QuinceLogoProps> = ({
  size = 'sm',
  breathing = false,
  className = '',
}) => {
  return (
    <span
      className={`inline-flex items-center justify-center shrink-0 select-none ${
        breathing ? 'animate-float-breathe' : ''
      } ${className}`}
    >
      <img
        src="/icons/quince-icon.svg"
        alt="Quince"
        className={`${SIZE_MAP[size]} object-contain drop-shadow-[0_2px_6px_rgba(249,175,73,0.22)]`}
        draggable={false}
      />
    </span>
  )
}
