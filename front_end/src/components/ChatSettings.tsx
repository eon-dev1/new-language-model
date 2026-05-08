/**
 * ChatSettings - LLM provider configuration panel within ChatDrawer.
 */

import React, { useState, useEffect } from 'react';
import {
  Box, Typography, TextField, IconButton, Divider, Select, MenuItem, ListSubheader,
  FormControl, InputLabel, Button, Alert, CircularProgress,
  Switch, FormControlLabel,
} from '@mui/material';
import { ArrowBack, Visibility, VisibilityOff } from '@mui/icons-material';
import { fetchChatConfig, saveChatConfig, testChatConnection, type ChatConfig } from '../renderer/api';
import { useSettings } from '../renderer/contexts/SettingsContext';

interface Props {
  onBack: () => void;
}

const ANTHROPIC_MODELS = [
  { id: 'claude-opus-4-6', label: 'Opus 4.6' },
  { id: 'claude-sonnet-4-6', label: 'Sonnet 4.6' },
  { id: 'claude-haiku-4-5-20251001', label: 'Haiku 4.5' },
];
const VALID_MODEL_IDS = new Set(ANTHROPIC_MODELS.map(m => m.id));

const OPENROUTER_MODELS = [
  { id: 'anthropic/claude-opus-4.6',   label: 'Opus 4.6',      group: 'Anthropic' },
  { id: 'anthropic/claude-sonnet-4.6', label: 'Sonnet 4.6',    group: 'Anthropic' },
  { id: 'anthropic/claude-haiku-4.5',  label: 'Haiku 4.5',     group: 'Anthropic' },
  { id: 'qwen/qwen3.5-397b-a17b',      label: 'Qwen 3.5 397B', group: 'Qwen' },
  { id: 'qwen/qwen3.5-35b-a3b',        label: 'Qwen 3.5 35B',  group: 'Qwen' },
];
const VALID_OPENROUTER_MODEL_IDS = new Set(OPENROUTER_MODELS.map(m => m.id));

export const ChatSettings: React.FC<Props> = ({ onBack }) => {
  const { settings, updateSettings } = useSettings();
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Form state
  const [provider, setProvider] = useState('anthropic');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('claude-sonnet-4-6');
  const [localUrl, setLocalUrl] = useState('http://127.0.0.1:8080');
  const [localModel, setLocalModel] = useState('default');
  const [showApiKey, setShowApiKey] = useState(false);
  const [openrouterKey, setOpenrouterKey] = useState('');
  const [openrouterModel, setOpenrouterModel] = useState('anthropic/claude-sonnet-4.6');
  const [showOpenrouterKey, setShowOpenrouterKey] = useState(false);
  const [thinkingEnabled, setThinkingEnabled] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await fetchChatConfig();
        setConfig(cfg);
        setProvider(cfg.llm_provider);
        setModel(VALID_MODEL_IDS.has(cfg.anthropic_model) ? cfg.anthropic_model : 'claude-sonnet-4-6');
        setLocalUrl(cfg.local_base_url);
        setLocalModel(cfg.local_model);
        setOpenrouterModel(VALID_OPENROUTER_MODEL_IDS.has(cfg.openrouter_model) ? cfg.openrouter_model : 'anthropic/claude-sonnet-4.6');
        setThinkingEnabled(cfg.thinking_enabled ?? true);
        // API keys are masked — don't populate the fields
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updates: Record<string, string | boolean> = {
        llm_provider: provider,
        anthropic_model: model,
        local_base_url: localUrl,
        local_model: localModel,
        openrouter_model: openrouterModel,
        thinking_enabled: thinkingEnabled,
      };
      if (apiKey) {
        updates.anthropic_api_key = apiKey;
      }
      if (openrouterKey) {
        updates.openrouter_api_key = openrouterKey;
      }
      await saveChatConfig(updates);
      setSuccess(true);
      setApiKey('');
      setOpenrouterKey('');
      // Refresh config to get updated preview
      const cfg = await fetchChatConfig();
      setConfig(cfg);
      setTimeout(() => setSuccess(false), 2000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, pb: 1 }}>
        <IconButton size="small" onClick={onBack}>
          <ArrowBack fontSize="small" />
        </IconButton>
        <Typography variant="subtitle2">Chat Settings</Typography>
      </Box>
      <Divider />

      <Box sx={{ flex: 1, overflowY: 'auto', p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
        {success && <Alert severity="success">Settings saved</Alert>}

        <FormControl fullWidth size="small">
          <InputLabel>Provider</InputLabel>
          <Select
            value={provider}
            label="Provider"
            onChange={e => setProvider(e.target.value)}
          >
            <MenuItem value="anthropic">Anthropic API</MenuItem>
            <MenuItem value="local">Local LLM</MenuItem>
            <MenuItem value="openrouter">OpenRouter</MenuItem>
          </Select>
        </FormControl>

        {provider === 'anthropic' && (
          <>
            <TextField
              fullWidth
              size="small"
              label={config?.has_api_key && !apiKey ? `API Key (saved: ${config.api_key_preview})` : 'API Key'}
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={config?.has_api_key ? 'Enter new key to replace' : 'Enter API key'}
              InputProps={{
                endAdornment: (
                  <IconButton size="small" onClick={() => setShowApiKey(!showApiKey)}>
                    {showApiKey ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                  </IconButton>
                ),
              }}
            />
            <FormControl fullWidth size="small">
              <InputLabel>Model</InputLabel>
              <Select
                value={model}
                label="Model"
                onChange={e => setModel(e.target.value)}
              >
                {ANTHROPIC_MODELS.map(m => (
                  <MenuItem key={m.id} value={m.id}>{m.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </>
        )}

        {provider === 'openrouter' && (
          <>
            <TextField
              fullWidth
              size="small"
              label={config?.has_openrouter_key && !openrouterKey ? `API Key (saved: ${config.openrouter_key_preview})` : 'API Key'}
              type={showOpenrouterKey ? 'text' : 'password'}
              value={openrouterKey}
              onChange={e => setOpenrouterKey(e.target.value)}
              placeholder={config?.has_openrouter_key ? 'Enter new key to replace' : 'Enter OpenRouter API key'}
              InputProps={{
                endAdornment: (
                  <IconButton size="small" onClick={() => setShowOpenrouterKey(!showOpenrouterKey)}>
                    {showOpenrouterKey ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                  </IconButton>
                ),
              }}
            />
            <FormControl fullWidth size="small">
              <InputLabel>Model</InputLabel>
              <Select
                value={openrouterModel}
                label="Model"
                onChange={e => setOpenrouterModel(e.target.value)}
              >
                <ListSubheader>Anthropic</ListSubheader>
                {OPENROUTER_MODELS.filter(m => m.group === 'Anthropic').map(m => (
                  <MenuItem key={m.id} value={m.id}>{m.label}</MenuItem>
                ))}
                <ListSubheader>Qwen</ListSubheader>
                {OPENROUTER_MODELS.filter(m => m.group === 'Qwen').map(m => (
                  <MenuItem key={m.id} value={m.id}>{m.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </>
        )}

        {provider === 'local' && (
          <>
            <TextField
              fullWidth
              size="small"
              label="Server URL"
              value={localUrl}
              onChange={e => setLocalUrl(e.target.value)}
              helperText="llama.cpp or Ollama endpoint"
            />
            <TextField
              fullWidth
              size="small"
              label="Model name"
              value={localModel}
              onChange={e => setLocalModel(e.target.value)}
              helperText="Model identifier for the local server"
            />
          </>
        )}

        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save settings'}
          </Button>
          <Button
            variant="outlined"
            onClick={async () => {
              setTesting(true);
              setTestResult(null);
              try {
                const result = await testChatConnection();
                setTestResult(result.success
                  ? { ok: true, message: 'Connection successful' }
                  : { ok: false, message: result.error || 'Connection failed' });
              } catch (err: any) {
                setTestResult({ ok: false, message: err.message });
              } finally {
                setTesting(false);
              }
            }}
            disabled={testing}
          >
            {testing ? <CircularProgress size={18} sx={{ mr: 0.5 }} /> : null}
            {testing ? 'Testing...' : 'Test Connection'}
          </Button>
        </Box>
        {testResult && (
          <Alert severity={testResult.ok ? 'success' : 'error'} onClose={() => setTestResult(null)}>
            {testResult.message}
          </Alert>
        )}

        <Divider sx={{ my: 1.5, borderColor: 'rgba(255,255,255,0.08)' }} />
        <Typography variant="caption" sx={{ opacity: 0.45, display: 'block', mb: 0.5, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Display
        </Typography>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={settings.toolPreviewEnabled}
              onChange={(e) => updateSettings({ toolPreviewEnabled: e.target.checked })}
            />
          }
          label={
            <Typography variant="body2" sx={{ opacity: 0.75 }}>
              Show tool data preview
            </Typography>
          }
        />
        <Divider sx={{ my: 1.5, borderColor: 'rgba(255,255,255,0.08)' }} />
        <Typography variant="caption" sx={{ opacity: 0.45, display: 'block', mb: 0.5, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          AI Thinking
        </Typography>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={thinkingEnabled}
              onChange={(e) => setThinkingEnabled(e.target.checked)}
            />
          }
          label={<Typography variant="body2" sx={{ opacity: 0.75 }}>Enable thinking modes</Typography>}
        />
        <Typography variant="caption" sx={{ opacity: 0.4, display: 'block', mt: 0.5 }}>
          When off, Think and Think Harder modes are hidden globally
        </Typography>
      </Box>
    </Box>
  );
};
