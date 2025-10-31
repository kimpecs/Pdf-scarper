export async function loadConfig(app) {
  try {
    const response = await fetch('/api/config');
    if (response.ok) {
      const config = await response.json();
      app.config = { ...app.config, ...config };
      console.log('Loaded frontend configuration:', app.config);
    }
  } catch (error) {
    console.error('Error loading config:', error);
  }
}
