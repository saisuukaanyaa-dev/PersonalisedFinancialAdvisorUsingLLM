// Builds the n8n credentials file from environment variables (runs inside the n8n image).
// The IDs match the ones the workflows reference, so no node needs re-linking after import.
const creds = [
  {
    id: 'DLigOZtLp73yVBeP', name: 'Postgres account', type: 'postgres',
    data: {
      host: 'postgres', port: 5432, database: process.env.PFA_PG_DB, user: process.env.PFA_PG_USER,
      password: process.env.PFA_PG_PASSWORD, ssl: 'disable', allowUnauthorizedCerts: false, sshTunnel: false,
    },
  },
  {
    id: 'X8YO6z75FjdGlh8o', name: 'OpenAI account', type: 'openAiApi',
    // A placeholder keeps the import valid; runs that call OpenAI fail until a real key is added to .env.
    data: { apiKey: process.env.OPENAI_API_KEY || 'not-set-add-OPENAI_API_KEY-to-env', url: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1' },
  },
  {
    id: 'pfaMcpBearer0001', name: 'PFA MCP bearer token', type: 'httpBearerAuth',
    data: { token: process.env.MCP_BEARER_TOKEN || 'change-me' },
  },
];
process.stdout.write(JSON.stringify(creds));
