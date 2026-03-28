import React from 'react';
import { IconButton } from '@mui/material';
import { ContentCopy, Check } from '@mui/icons-material';

interface CopyIconButtonProps {
  text: string;
  size?: number; // icon px, default 16
}

export const CopyIconButton: React.FC<CopyIconButtonProps> = ({ text, size = 16 }) => {
  const [copied, setCopied] = React.useState(false);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 1500);
    } catch { /* silent */ }
  };

  React.useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  return (
    <IconButton
      size="small"
      onClick={handleCopy}
      aria-label="Copy"
      sx={{
        color: copied ? 'success.main' : 'rgba(255,255,255,0.35)',
        '&:hover': { color: copied ? 'success.main' : 'rgba(255,255,255,1)' },
        flexShrink: 0,
      }}
    >
      {copied
        ? <Check sx={{ fontSize: size }} />
        : <ContentCopy sx={{ fontSize: size }} />
      }
    </IconButton>
  );
};
