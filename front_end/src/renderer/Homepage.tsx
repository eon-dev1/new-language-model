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
import { TypewriterText } from './TypewriterText';
import { NewProjectDialog } from '../components/NewProjectDialog';
import { LanguageProject } from '../components/LanguageProject';
import { LanguageProject as LanguageProjectType } from './types/LanguageProject';

// Define the Project interface.
// Maps language data from the API to a project with verification progress.
interface Project {
  id: string;
  name: string;
  languageCode: string;
  totalVerses: number;
  verifiedCount: number;
  verificationProgress: number;  // 0-100 percentage
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
  const [selectedProject, setSelectedProject] = useState<LanguageProjectType | null>(null);

  useEffect(() => {
    /**
     * loadLanguages asynchronously fetches languages using the API module.
     * It then maps the returned languages to our Project interface,
     * using the index as a simple unique id.
     */
    const loadLanguages = async () => {
      try {
        const languages = await fetchLanguages();
        // Filter out base language (English) - it's not a translation project
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
      } catch (err) {
        // If fetch fails, update error state.
        setError('Failed to load languages. Please check if the backend is running.');
      } finally {
        // Always stop the loading spinner, irrespective of success or failure.
        setLoading(false);
      }
    };

    loadLanguages();
  }, []);

  /**
   * handleCreateNew - Opens the new project dialog.
   */
  const handleCreateNew = () => {
    console.log('[Homepage] handleCreateNew called, setting dialog open to true');
    setNewProjectDialogOpen(true);
  };

  /**
   * handleNewProjectSuccess - Called when a new project is successfully created.
   * Refreshes the language list.
   */
  const handleNewProjectSuccess = async (languageCode: string) => {
    console.log(`New project created: ${languageCode}`);
    // Refresh the languages list
    try {
      const languages = await fetchLanguages();
      // Filter out base language (English) - it's not a translation project
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
      lastAccessed: new Date(),
      progress: {
        humanBibleCompletion: project.verificationProgress,
        nlmBibleCompletion: 0,
        dictionaryCompletion: 0,
        grammarCompletion: 0
      }
    };

    setSelectedProject(languageProject);
  };

  /**
   * handleBackFromProject - Called when navigating back from project view.
   */
  const handleBackFromProject = () => {
    setSelectedProject(null);
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
        py: 8,
        px: 4,
      }}
    >
      <Container maxWidth="lg">
        <motion.div initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <Typography variant="h1" align="center" gutterBottom>
            New Language Model
          </Typography>
          <Typography
            variant="subtitle1"
            align="center"
            color="text.secondary"
            sx={{ mb: 6, fontSize: '2rem' }}
          >
            <TypewriterText text="To whom much has been given, much is required." speed={25} />
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
          <Grid container spacing={4}>
            <Grid item xs={12} md={6}>
              <Paper elevation={3} sx={{ p: 4, borderRadius: '16px' }}>
                <Typography variant="h2" gutterBottom>
                  Continue Journey...
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
                                {project.verificationProgress.toFixed(1)}% verified
                              </Typography>
                            </Box>
                            <LinearProgress
                              variant="determinate"
                              value={project.verificationProgress}
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

            <Grid item xs={12} md={6} display="flex" alignItems="center" justifyContent="center">
              <Paper elevation={3} sx={{ p: 4, borderRadius: '16px', textAlign: 'center' }}>
                <Typography variant="h2" gutterBottom>
                  Start Fresh
                </Typography>
                <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    size="large"
                    onClick={handleCreateNew}
                    sx={{ px: 6, py: 2 }}
                  >
                    Create New Project
                  </Button>
                </motion.div>
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
    </Box>
  );
}