// components/LanguageProject.tsx
// Main language project view with resource navigation

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Container,
  Grid,
  LinearProgress,
  Chip,
  IconButton
} from '@mui/material';
import {
  ArrowBack,
  MenuBook,
  Book,
  School
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { LanguageProject as LanguageProjectType, ResourceType } from '../renderer/types/LanguageProject';
import { BibleReader } from './BibleReader';
import { DictionaryViewer } from './DictionaryViewer';
import { GrammarViewer } from './GrammarViewer';

interface LanguageProjectProps {
  project: LanguageProjectType;
  onBack: () => void;
}

export function LanguageProject({ project, onBack }: LanguageProjectProps) {
  const [selectedResource, setSelectedResource] = useState<ResourceType | null>(null);

  const handleResourceSelect = (resourceType: ResourceType) => {
    console.log(`[LanguageProject] Selected resource: ${resourceType} for ${project.language.name}`);
    setSelectedResource(resourceType);
  };

  const handleBackToResources = () => {
    setSelectedResource(null);
  };

  // Resource configuration - unified views (3 cards instead of 5)
  const resourceConfig = [
    {
      type: 'bible' as ResourceType,
      title: 'Bible',
      subtitle: 'Scripture with side-by-side translation',
      icon: <MenuBook sx={{ fontSize: 40 }} />,
      available: project.resources.bible?.available || false,
      color: '#4CAF50'
    },
    {
      type: 'dictionary' as ResourceType,
      title: 'Dictionary',
      subtitle: 'Unified human & AI dictionary',
      icon: <Book sx={{ fontSize: 40 }} />,
      available: project.resources.dictionary?.available ||
                 project.resources.humanDictionary?.available ||
                 project.resources.nlmDictionary?.available ||
                 true, // Default to available for new unified view
      color: '#2196F3'
    },
    {
      type: 'grammar' as ResourceType,
      title: 'Grammar',
      subtitle: 'Unified human & AI grammar system',
      icon: <School sx={{ fontSize: 40 }} />,
      available: project.resources.grammar?.available ||
                 project.resources.humanGrammar?.available ||
                 project.resources.nlmGrammar?.available ||
                 true, // Default to available for new unified view
      color: '#9C27B0'
    }
  ];

  // Route to appropriate viewer based on selected resource
  if (selectedResource === 'bible') {
    return (
      <BibleReader
        languageCode={project.language.code || project.language.id}
        languageName={project.language.name}
        onBack={handleBackToResources}
      />
    );
  }

  if (selectedResource === 'dictionary') {
    return (
      <DictionaryViewer
        languageCode={project.language.code || project.language.id}
        languageName={project.language.name}
        onBack={handleBackToResources}
      />
    );
  }

  if (selectedResource === 'grammar') {
    return (
      <GrammarViewer
        languageCode={project.language.code || project.language.id}
        languageName={project.language.name}
        onBack={handleBackToResources}
      />
    );
  }

  // Main project overview with resource selection
  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #1A1A1A, #2D2D2D)',
        pt: 7,  // 56px to clear fixed TopBar (48px)
        pb: 4,
      }}
    >
      <Container maxWidth="lg">
        {/* Header with back button */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 4 }}>
          <IconButton onClick={onBack} sx={{ mr: 2, color: 'white' }}>
            <ArrowBack />
          </IconButton>
          <Typography variant="h3" component="h1" sx={{ color: 'white' }}>
            {project.language.name}
          </Typography>
          {project.language.code && (
            <Chip
              label={project.language.code}
              sx={{ ml: 2, bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
            />
          )}
        </Box>

        {/* Progress Overview */}
        <Paper elevation={3} sx={{ p: 3, mb: 4, bgcolor: 'rgba(255,255,255,0.05)' }}>
          <Typography variant="h6" gutterBottom sx={{ color: 'white' }}>
            Project Progress
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                Bible Verification: {project.progress.humanBibleCompletion}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={project.progress.humanBibleCompletion}
                sx={{ mt: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                Dictionary & Grammar: {Math.round((project.progress.dictionaryCompletion + project.progress.grammarCompletion) / 2)}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.round((project.progress.dictionaryCompletion + project.progress.grammarCompletion) / 2)}
                sx={{ mt: 1 }}
              />
            </Grid>
          </Grid>
        </Paper>

        {/* Resource Grid */}
        <Typography variant="h4" gutterBottom sx={{ color: 'white', mb: 3 }}>
          Project Resources
        </Typography>

        <Grid container spacing={3}>
          {resourceConfig.map((resource) => (
            <Grid item xs={12} sm={6} md={4} key={resource.type}>
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Paper
                  elevation={3}
                  sx={{
                    p: 3,
                    height: '200px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    bgcolor: resource.available
                      ? 'rgba(255,255,255,0.05)'
                      : 'rgba(255,255,255,0.02)',
                    border: resource.available
                      ? `2px solid ${resource.color}`
                      : '2px solid rgba(255,255,255,0.1)',
                    opacity: resource.available ? 1 : 0.6,
                    transition: 'all 0.3s ease',
                    '&:hover': {
                      bgcolor: resource.available
                        ? 'rgba(255,255,255,0.1)'
                        : 'rgba(255,255,255,0.05)',
                    }
                  }}
                  onClick={() => resource.available && handleResourceSelect(resource.type)}
                >
                  <Box sx={{ color: resource.color, mb: 2 }}>
                    {resource.icon}
                  </Box>
                  <Typography
                    variant="h6"
                    align="center"
                    gutterBottom
                    sx={{ color: 'white' }}
                  >
                    {resource.title}
                  </Typography>
                  <Typography
                    variant="body2"
                    align="center"
                    sx={{ color: 'rgba(255,255,255,0.7)' }}
                  >
                    {resource.subtitle}
                  </Typography>
                  {!resource.available && (
                    <Chip
                      label="Coming Soon"
                      size="small"
                      sx={{
                        mt: 1,
                        bgcolor: 'rgba(255,255,255,0.1)',
                        color: 'rgba(255,255,255,0.7)'
                      }}
                    />
                  )}
                </Paper>
              </motion.div>
            </Grid>
          ))}
        </Grid>

        {/* Last Accessed Info */}
        <Paper elevation={1} sx={{ p: 2, mt: 4, bgcolor: 'rgba(255,255,255,0.02)' }}>
          <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)' }}>
            Last accessed: {project.lastAccessed.toLocaleDateString()}
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
}
