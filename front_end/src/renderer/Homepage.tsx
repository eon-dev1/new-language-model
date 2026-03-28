import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  List,
  ListItem,
  Paper,
  Container,
  Grid,
  CircularProgress,
  LinearProgress
} from '@mui/material';
import { motion } from 'framer-motion';
import { fetchLanguages, Language } from './api';
import { NewProjectDialog } from '../components/NewProjectDialog';
import { BaseLanguageDialog } from '../components/BaseLanguageDialog';
import { LanguageProject } from '../components/LanguageProject';
import { LanguageProject as LanguageProjectType } from './types/LanguageProject';
import { useChat } from './contexts/ChatContext';
import { TOPBAR_HEIGHT } from './constants';

// Verification progress breakdown by testament
interface VerificationProgress {
  old_testament: number;  // 0-100 percentage
  new_testament: number;  // 0-100 percentage
  total: number;          // 0-100 percentage
}

// Define the Project interface.
// Maps language data from the API to a project with verification progress.
interface Project {
  id: string;
  name: string;
  languageCode: string;
  totalVerses: number;
  verifiedCount: number;
  verificationProgress: VerificationProgress;
  isBaseLanguage: boolean;
}

/**
 * Homepage component that loads the list of languages from the API and renders them.
 * Displays a loading spinner while fetching the data, and shows error messages if any.
 */
export function Homepage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true); // Loading state for API call
  const [error, setError] = useState<string | null>(null); // Error state for API failure
  const [newProjectDialogOpen, setNewProjectDialogOpen] = useState(false);
  const [baseLanguageDialogOpen, setBaseLanguageDialogOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<LanguageProjectType | null>(null);
  const [hasAutoResumed, setHasAutoResumed] = useState(false);
  const { setAppContext } = useChat();

  const loadAndSetProjects = async () => {
    const languages = await fetchLanguages();
    const translationLanguages = languages.filter((lang: Language) => !lang.is_base_language);
    const mappedProjects: Project[] = translationLanguages.map((lang: Language) => ({
      id: lang.language_code,
      name: lang.language_name,
      languageCode: lang.language_code,
      totalVerses: lang.total_verses,
      verifiedCount: lang.verified_count,
      verificationProgress: lang.verification_progress,
      isBaseLanguage: lang.is_base_language,
    }));
    setProjects(mappedProjects);
  };

  useEffect(() => {
    const loadInitial = async () => {
      try {
        await loadAndSetProjects();
      } catch (err) {
        setError('Failed to load languages. Please check if the backend is running.');
      } finally {
        setLoading(false);
      }
    };

    loadInitial();
  }, []);

  // Auto-resume last selected language
  useEffect(() => {
    if (loading || projects.length === 0 || hasAutoResumed) return;

    try {
      const lastCode = localStorage.getItem('lastLanguageCode');
      if (!lastCode) {
        setHasAutoResumed(true);
        return;
      }

      const project = projects.find(p => p.languageCode === lastCode);
      if (project) {
        console.log('[Homepage] Auto-resuming language:', lastCode);
        handleSelectProject(project);
      }
      setHasAutoResumed(true);
    } catch (err) {
      console.warn('Failed to auto-resume language:', err);
      setHasAutoResumed(true);
    }
  }, [loading, projects, hasAutoResumed]);

  /**
   * handleCreateNew - Opens the new project dialog.
   */
  const handleCreateNew = () => {
    console.log('[Homepage] handleCreateNew called, setting dialog open to true');
    setNewProjectDialogOpen(true);
  };

  const handleChooseBaseLanguage = () => {
    setBaseLanguageDialogOpen(true);
  };

  /**
   * handleNewProjectSuccess - Called when a new project is successfully created.
   * Refreshes the language list.
   */
  const handleNewProjectSuccess = async (languageCode: string) => {
    console.log(`New project created: ${languageCode}`);
    try {
      await loadAndSetProjects();
    } catch (err) {
      console.error('Failed to refresh languages after project creation');
    }
  };

  /**
   * handleSelectProject - Called when a language (project) is selected.
   * Transforms the flat Project to nested LanguageProjectType for LanguageProject component.
   * @param {Project} project - The project selected.
   */
  const handleSelectProject = (project: Project) => {
    console.log('Selected project:', project);

    // Persist to localStorage for auto-resume
    try {
      localStorage.setItem('lastLanguageCode', project.languageCode);
    } catch (err) {
      console.warn('Failed to save last language:', err);
    }

    // Transform flat Project to nested LanguageProjectType
    const languageProject: LanguageProjectType = {
      language: {
        id: project.id,
        name: project.name,
        code: project.languageCode
      },
      resources: {
        bible: { available: true, books: [] },
        humanDictionary: null,
        nlmDictionary: null,
        humanGrammar: null,
        nlmGrammar: null
      },
      progress: {
        oldTestamentCompletion: project.verificationProgress.old_testament,
        newTestamentCompletion: project.verificationProgress.new_testament,
        overallCompletion: project.verificationProgress.total
      }
    };

    setSelectedProject(languageProject);
  };

  /**
   * handleBackFromProject - Called when navigating back from project view.
   */
  const handleBackFromProject = () => {
    setSelectedProject(null);
    setAppContext({
      languageCode: null,
      bookCode: null,
      chapter: null,
      view: null,
    });
  };

  // If a project is selected, show the LanguageProject view
  if (selectedProject) {
    return (
      <LanguageProject
        project={selectedProject}
        onBack={handleBackFromProject}
      />
    );
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #000000, #1A1A1A)',
        pt: `${TOPBAR_HEIGHT + 16}px`,
        pb: 8,
        px: 4,
      }}
    >
      <Container maxWidth="lg">
        <motion.div initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <Typography variant="h1" align="center" gutterBottom>
            New Language Model
          </Typography>
         </motion.div>

        {loading ? (
          // Show a spinner while loading data
          <Box display="flex" justifyContent="center" my={4}>
            <CircularProgress color="primary" />
          </Box>
        ) : error ? (
          // Display error message if loading fails
          <Typography color="error" align="center">
            {error}
          </Typography>
        ) : (
          <Grid container spacing={4} sx={{ minHeight: '60vh', alignItems: 'center' }}>
            <Grid item xs={12} md={6}>
              <Paper elevation={3} sx={{ p: 4, borderRadius: '16px' }}>
                <Typography variant="h2" gutterBottom>
                  Continue...
                </Typography>
                {projects.length > 0 ? (
                  <List>
                    {projects.map((project) => (
                      <motion.li key={project.id} whileHover={{ scale: 1.02 }}>
                        <ListItem disablePadding>
                          <Button
                            fullWidth
                            variant="outlined"
                            onClick={() => handleSelectProject(project)}
                            sx={{
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: 'stretch',
                              mb: 2,
                              p: 2,
                            }}
                            disableFocusRipple
                            disableRipple
                          >
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mb: 1 }}>
                              <Typography sx={{ fontSize: '1.5rem', textTransform: 'none' }}>
                                {project.name}
                              </Typography>
                              <Typography sx={{ fontSize: '1rem', color: 'text.secondary' }}>
                                {project.verificationProgress.total.toFixed(1)}% verified
                              </Typography>
                            </Box>
                            <LinearProgress
                              variant="determinate"
                              value={project.verificationProgress.total}
                              sx={{
                                width: '100%',
                                height: 8,
                                borderRadius: 4,
                                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                                '& .MuiLinearProgress-bar': {
                                  borderRadius: 4,
                                },
                              }}
                            />
                          </Button>
                        </ListItem>
                      </motion.li>
                    ))}
                  </List>
                ) : (
                  <Typography color="text.secondary">No projects available.</Typography>
                )}
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper elevation={3} sx={{ p: 4, borderRadius: '16px' }}>
                <Typography variant="h2" gutterBottom>
                  Create New...
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    color="primary"
                    size="large"
                    fullWidth
                    onClick={handleCreateNew}
                    sx={{ py: 3, fontSize: '1.5rem' }}
                  >
                    Create New Project
                  </Button>
                  <Button
                    variant="outlined"
                    color="primary"
                    size="large"
                    fullWidth
                    onClick={handleChooseBaseLanguage}
                    sx={{ py: 3, fontSize: '1.5rem' }}
                  >
                    Choose Base Languages
                  </Button>
                </Box>
              </Paper>
            </Grid>
          </Grid>
        )}
      </Container>

      <NewProjectDialog
        open={newProjectDialogOpen}
        onClose={() => setNewProjectDialogOpen(false)}
        onSuccess={handleNewProjectSuccess}
      />
      <BaseLanguageDialog
        open={baseLanguageDialogOpen}
        onClose={() => setBaseLanguageDialogOpen(false)}
      />
    </Box>
  );
}