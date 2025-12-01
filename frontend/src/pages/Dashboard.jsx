import React, { useState, useEffect } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  TrendingUp,
  TrendingDown,
  Warning,
  CheckCircle,
  Refresh,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { useSnackbar } from 'notistack';

// Components
import MetricCard from '../components/Cards/MetricCard';
import AlertCard from '../components/Cards/AlertCard';
import Loading from '../components/Common/Loading';

// Services
import { api } from '../services/api';
import { useWebSocket } from '../services/websocket';

const Dashboard = () => {
  const theme = useTheme();
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [performanceData, setPerformanceData] = useState([]);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [activityData, setActivityData] = useState([]);

  // WebSocket for real-time updates
  const { lastMessage } = useWebSocket();

  useEffect(() => {
    fetchDashboardData();
  }, []);

  useEffect(() => {
    if (lastMessage) {
      handleWebSocketMessage(lastMessage);
    }
  }, [lastMessage]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      const [statsRes, performanceRes, alertsRes, activityRes] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/dashboard/performance/top?limit=5'),
        api.get('/alerts?limit=5&status=open'),
        api.get('/dashboard/activity/recent?limit=10'),
      ]);

      setStats(statsRes.data);
      setPerformanceData(performanceRes.data);
      setRecentAlerts(alertsRes.data);
      setActivityData(activityRes.data);

    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      enqueueSnackbar('Failed to load dashboard data', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleWebSocketMessage = (message) => {
    if (message.type === 'alert') {
      enqueueSnackbar(`New alert: ${message.data.title}`, { 
        variant: message.data.severity === 'critical' ? 'error' : 'warning' 
      });
      
      // Refresh alerts
      fetchRecentAlerts();
    } else if (message.type === 'metric_update') {
      // Refresh performance data
      fetchPerformanceData();
    }
  };

  const fetchRecentAlerts = async () => {
    try {
      const res = await api.get('/alerts?limit=5&status=open');
      setRecentAlerts(res.data);
    } catch (error) {
      console.error('Error fetching alerts:', error);
    }
  };

  const fetchPerformanceData = async () => {
    try {
      const res = await api.get('/dashboard/performance/top?limit=5');
      setPerformanceData(res.data);
    } catch (error) {
      console.error('Error fetching performance data:', error);
    }
  };

  const handleRefresh = () => {
    fetchDashboardData();
    enqueueSnackbar('Dashboard refreshed', { variant: 'info' });
  };

  if (loading) {
    return <Loading />;
  }

  // Chart data
  const assetTypeData = [
    { name: 'Financial', value: 65, color: '#2196f3' },
    { name: 'Manufacturing', value: 35, color: '#4caf50' },
  ];

  const alertSeverityData = [
    { name: 'Critical', value: stats?.critical_alerts || 0, color: '#f44336' },
    { name: 'High', value: 5, color: '#ff9800' },
    { name: 'Medium', value: 8, color: '#ffeb3b' },
    { name: 'Low', value: 12, color: '#4caf50' },
  ];

  const performanceChartData = performanceData.map((asset, index) => ({
    name: asset.asset_name.substring(0, 10) + '...',
    value: asset.health_score,
    dailyChange: asset.daily_change,
  }));

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <DashboardIcon sx={{ fontSize: 32 }} />
          <Typography variant="h4" component="h1">
            Dashboard
          </Typography>
        </Box>
        <IconButton onClick={handleRefresh} color="primary">
          <Refresh />
        </IconButton>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Assets"
            value={stats?.total_assets || 0}
            icon={<DashboardIcon />}
            color="#2196f3"
            change={+12}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Active Assets"
            value={stats?.active_assets || 0}
            icon={<CheckCircle />}
            color="#4caf50"
            change={+5}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Open Alerts"
            value={stats?.open_alerts || 0}
            icon={<Warning />}
            color="#ff9800"
            change={-3}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Avg Health Score"
            value={`${stats?.avg_health_score || 0}%`}
            icon={<TrendingUp />}
            color="#9c27b0"
            change={+2.5}
            isPercentage
          />
        </Grid>
      </Grid>

      {/* Main Content */}
      <Grid container spacing={3}>
        {/* Left Column */}
        <Grid item xs={12} lg={8}>
          {/* Performance Chart */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Performing Assets
            </Typography>
            <Box sx={{ height: 300 }}>
              <LineChart
                width={800}
                height={300}
                data={performanceChartData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#2196f3"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </Box>
          </Paper>

          {/* Recent Alerts */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Warning /> Recent Alerts
            </Typography>
            {recentAlerts.length > 0 ? (
              recentAlerts.map((alert) => (
                <AlertCard key={alert.id} alert={alert} />
              ))
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                No active alerts
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Right Column */}
        <Grid item xs={12} lg={4}>
          {/* Asset Distribution */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Asset Distribution
            </Typography>
            <Box sx={{ height: 200, display: 'flex', justifyContent: 'center' }}>
              <PieChart width={200} height={200}>
                <Pie
                  data={assetTypeData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {assetTypeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </Box>
          </Paper>

          {/* Alert Severity */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Alert Severity Distribution
            </Typography>
            <Box sx={{ height: 200 }}>
              <BarChart
                width={300}
                height={200}
                data={alertSeverityData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <Bar dataKey="value" fill="#8884d8">
                  {alertSeverityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </Box>
          </Paper>

          {/* Recent Activity */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Recent Activity
            </Typography>
            <Box sx={{ maxHeight: 300, overflowY: 'auto' }}>
              {activityData.map((activity, index) => (
                <Box
                  key={index}
                  sx={{
                    py: 1,
                    borderBottom: index < activityData.length - 1 ? '1px solid rgba(255, 255, 255, 0.1)' : 'none',
                  }}
                >
                  <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {activity.type === 'alert' ? (
                      <Warning sx={{ fontSize: 16, color: '#ff9800' }} />
                    ) : (
                      <TrendingUp sx={{ fontSize: 16, color: '#4caf50' }} />
                    )}
                    {activity.title || `${activity.type} update`}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(activity.timestamp).toLocaleString()}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
