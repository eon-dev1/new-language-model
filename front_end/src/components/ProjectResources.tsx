// components/ProjectResources.tsx
// Resource viewer component for displaying specific project resources

import React from 'react';
import {
  Box,
  Typography,
  IconButton,
  Container,
  Paper,
  Chip
} from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { LanguageProject, ResourceType } from '../renderer/types/LanguageProject';

interface ProjectResourcesProps {
  project: LanguageProject;
  resourceType: ResourceType;
  onBack: () => void;
}

export function ProjectResources({ project, resourceType, onBack }: ProjectResourcesProps) {
  const getResourceTitle = (type: ResourceType): string => {
    switch (type) {
      case 'bible':
        return 'Bible';
      case 'humanDictionary':
        return 'Human Dictionary';
      case 'nlmDictionary':
        return 'NLM Dictionary';
      case 'humanGrammar':
        return 'Human Grammar';
      case 'nlmGrammar':
        return 'NLM Grammar';
      default:
        return 'Resource';
    }
  };

  const getResourceData = () => {
    switch (resourceType) {
      case 'bible':
        return project.resources.bible;
      case 'humanDictionary':
        return project.resources.humanDictionary;
      case 'nlmDictionary':
        return project.resources.nlmDictionary;
      case 'humanGrammar':
        return project.resources.humanGrammar;
      case 'nlmGrammar':
        return project.resources.nlmGrammar;
      default:
        return null;
    }
  };

  const resourceData = getResourceData();
  const resourceTitle = getResourceTitle(resourceType);

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
            {resourceTitle}
          </Typography>
          <Chip 
            label={project.language.name} 
            sx={{ ml: 2, bgcolor: 'rgba(255,255,255,0.1)', color: 'white' }}
          />
        </Box>

        {/* Resource Content */}
        <Paper elevation={3} sx={{ p: 4, bgcolor: 'rgba(255,255,255,0.05)' }}>
          {resourceData ? (
            <Box>
              <Typography variant="h5" gutterBottom sx={{ color: 'white' }}>
                {resourceData.title}
              </Typography>

              {'version' in resourceData && resourceData.version && (
                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)', mb: 2 }}>
                  Version: {resourceData.version}
                </Typography>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" sx={{ color: 'white', mb: 2 }}>
                  Resource Details
                </Typography>
                
                {resourceType === 'bible' && 'books' in resourceData && (
                  <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                    Contains {resourceData.books?.length || 0} books
                  </Typography>
                )}
                
                {(resourceType.includes('Dictionary') || resourceType.includes('Grammar')) && 'type' in resourceData && (
                  <Chip 
                    label={resourceData.type === 'human' ? 'Human-authored' : 'AI-generated'} 
                    sx={{ 
                      bgcolor: resourceData.type === 'human' ? 'rgba(76,175,80,0.2)' : 'rgba(255,152,0,0.2)', 
                      color: 'white' 
                    }}
                  />
                )}
              </Box>

              {/* Placeholder for future resource content */}
              <Box sx={{ mt: 4, p: 3, bgcolor: 'rgba(255,255,255,0.02)', borderRadius: 1 }}>
                <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.6)', textAlign: 'center' }}>
                  Resource content viewer will be implemented here.
                  <br />
                  This will display the actual {resourceTitle.toLowerCase()} content for {project.language.name}.
                </Typography>
              </Box>
            </Box>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="h6" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                This resource is not yet available for {project.language.name}
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)', mt: 1 }}>
                Please check back later or contact support for more information.
              </Typography>
            </Box>
          )}
        </Paper>
      </Container>
    </Box>
  );
}