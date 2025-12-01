import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  IconButton,
  Button,
  TextField,
  InputAdornment,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Search,
  Add,
  Edit,
  Delete,
  Visibility,
  TrendingUp,
  TrendingDown,
  Factory,
  AccountBalance,
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';
import { useSnackbar } from 'notistack';

// Components
import Loading from '../components/Common/Loading';

// Services
import { api } from '../services/api';

const Assets = () => {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(true);
  const [assets, setAssets] = useState([]);
  const [filteredAssets, setFilteredAssets] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [assetTypeFilter, setAssetTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    asset_type: 'financial',
    status: 'active',
    location: '',
    symbol: '',
    current_price: '',
    quantity: '',
  });

  // DataGrid columns
  const columns = [
    { 
      field: 'name', 
      headerName: 'Name', 
      width: 200,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {params.row.asset_type === 'financial' ? (
            <AccountBalance sx={{ color: '#2196f3' }} />
          ) : (
            <Factory sx={{ color: '#4caf50' }} />
          )}
          {params.value}
        </Box>
      )
    },
    { field: 'symbol', headerName: 'Symbol', width: 120 },
    { field: 'asset_type', headerName: 'Type', width: 120,
      renderCell: (params) => (
        <Chip 
          label={params.value} 
          color={params.value === 'financial' ? 'primary' : 'success'}
          size="small"
        />
      )
    },
    { field: 'status', headerName: 'Status', width: 120,
      renderCell: (params) => {
        const colorMap = {
          active: 'success',
          inactive: 'default',
          maintenance: 'warning',
          failed: 'error',
        };
        return (
          <Chip 
            label={params.value} 
            color={colorMap[params.value] || 'default'}
            size="small"
          />
        );
      }
    },
    { field: 'current_price', headerName: 'Current Price', width: 120,
      renderCell: (params) => params.row.asset_type === 'financial' ? `$${params.value}` : '-'
    },
    { field: 'health_score', headerName: 'Health Score', width: 140,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: '100%', mr: 1 }}>
            <LinearProgress 
              variant="determinate" 
              value={params.value} 
              color={
                params.value >= 80 ? 'success' :
                params.value >= 60 ? 'warning' : 'error'
              }
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
          <Typography variant="body2">{params.value}%</Typography>
        </Box>
      )
    },
    { field: 'created_at', headerName: 'Created', width: 150,
      valueGetter: (params) => new Date(params.value).toLocaleDateString()
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 150,
      renderCell: (params) => (
        <Box>
          <IconButton size="small" onClick={() => handleView(params.row)}>
            <Visibility fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={() => handleEdit(params.row)}>
            <Edit fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={() => handleDelete(params.row)}>
            <Delete fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  useEffect(() => {
    fetchAssets();
  }, []);

  useEffect(() => {
    filterAssets();
  }, [assets, searchTerm, assetTypeFilter, statusFilter]);

  const fetchAssets = async () => {
    try {
      setLoading(true);
      const response = await api.get('/assets');
      setAssets(response.data);
    } catch (error) {
      console.error('Error fetching assets:', error);
      enqueueSnackbar('Failed to load assets', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const filterAssets = () => {
    let filtered = assets;

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(asset =>
        asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        asset.symbol?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        asset.description?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Asset type filter
    if (assetTypeFilter !== 'all') {
      filtered = filtered.filter(asset => asset.asset_type === assetTypeFilter);
    }

    // Status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(asset => asset.status === statusFilter);
    }

    setFilteredAssets(filtered);
  };

  const handleSearch = (event) => {
    setSearchTerm(event.target.value);
  };

  const handleView = (asset) => {
    // Navigate to asset detail page
    console.log('View asset:', asset);
  };

  const handleEdit = (asset) => {
    setSelectedAsset(asset);
    setFormData({
      name: asset.name,
      description: asset.description || '',
      asset_type: asset.asset_type,
      status: asset.status,
      location: asset.location || '',
      symbol: asset.symbol || '',
      current_price: asset.current_price || '',
      quantity: asset.quantity || '',
    });
    setOpenDialog(true);
  };

  const handleDelete = async (asset) => {
    if (window.confirm(`Are you sure you want to delete ${asset.name}?`)) {
      try {
        await api.delete(`/assets/${asset.id}`);
        enqueueSnackbar('Asset deleted successfully', { variant: 'success' });
        fetchAssets();
      } catch (error) {
        console.error('Error deleting asset:', error);
        enqueueSnackbar('Failed to delete asset', { variant: 'error' });
      }
    }
  };

  const handleCreate = () => {
    setSelectedAsset(null);
    setFormData({
      name: '',
      description: '',
      asset_type: 'financial',
      status: 'active',
      location: '',
      symbol: '',
      current_price: '',
      quantity: '',
    });
    setOpenDialog(true);
  };

  const handleSubmit = async () => {
    try {
      if (selectedAsset) {
        // Update existing asset
        await api.put(`/assets/${selectedAsset.id}`, formData);
        enqueueSnackbar('Asset updated successfully', { variant: 'success' });
      } else {
        // Create new asset
        await api.post('/assets', formData);
        enqueueSnackbar('Asset created successfully', { variant: 'success' });
      }
      setOpenDialog(false);
      fetchAssets();
    } catch (error) {
      console.error('Error saving asset:', error);
      enqueueSnackbar('Failed to save asset', { variant: 'error' });
    }
  };

  const handleFormChange = (event) => {
    setFormData({
      ...formData,
      [event.target.name]: event.target.value,
    });
  };

  if (loading) {
    return <Loading />;
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Assets
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreate}
        >
          Add Asset
        </Button>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder="Search assets..."
              value={searchTerm}
              onChange={handleSearch}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={6} md={3}>
            <FormControl fullWidth>
              <InputLabel>Asset Type</InputLabel>
              <Select
                value={assetTypeFilter}
                onChange={(e) => setAssetTypeFilter(e.target.value)}
                label="Asset Type"
              >
                <MenuItem value="all">All Types</MenuItem>
                <MenuItem value="financial">Financial</MenuItem>
                <MenuItem value="manufacturing">Manufacturing</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6} md={3}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                label="Status"
              >
                <MenuItem value="all">All Status</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
                <MenuItem value="maintenance">Maintenance</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      {/* Stats Summary */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Total Assets
              </Typography>
              <Typography variant="h4">
                {assets.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Financial Assets
              </Typography>
              <Typography variant="h4" sx={{ color: '#2196f3' }}>
                {assets.filter(a => a.asset_type === 'financial').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Manufacturing Assets
              </Typography>
              <Typography variant="h4" sx={{ color: '#4caf50' }}>
                {assets.filter(a => a.asset_type === 'manufacturing').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Avg Health Score
              </Typography>
              <Typography variant="h4">
                {assets.length > 0 
                  ? `${(assets.reduce((sum, a) => sum + a.health_score, 0) / assets.length).toFixed(1)}%`
                  : '0%'
                }
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Data Grid */}
      <Paper sx={{ height: 600, width: '100%' }}>
        <DataGrid
          rows={filteredAssets}
          columns={columns}
          pageSize={10}
          rowsPerPageOptions={[10, 25, 50]}
          checkboxSelection
          disableSelectionOnClick
          getRowId={(row) => row.id}
        />
      </Paper>

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedAsset ? 'Edit Asset' : 'Create New Asset'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Name"
                name="name"
                value={formData.name}
                onChange={handleFormChange}
                required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                name="description"
                value={formData.description}
                onChange={handleFormChange}
                multiline
                rows={3}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Asset Type</InputLabel>
                <Select
                  name="asset_type"
                  value={formData.asset_type}
                  onChange={handleFormChange}
                  label="Asset Type"
                >
                  <MenuItem value="financial">Financial</MenuItem>
                  <MenuItem value="manufacturing">Manufacturing</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  name="status"
                  value={formData.status}
                  onChange={handleFormChange}
                  label="Status"
                >
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="inactive">Inactive</MenuItem>
                  <MenuItem value="maintenance">Maintenance</MenuItem>
                  <MenuItem value="failed">Failed</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            {formData.asset_type === 'financial' && (
              <>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Symbol"
                    name="symbol"
                    value={formData.symbol}
                    onChange={handleFormChange}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Current Price"
                    name="current_price"
                    type="number"
                    value={formData.current_price}
                    onChange={handleFormChange}
                    InputProps={{
                      startAdornment: <InputAdornment position="start">$</InputAdornment>,
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Quantity"
                    name="quantity"
                    type="number"
                    value={formData.quantity}
                    onChange={handleFormChange}
                  />
                </Grid>
              </>
            )}
            {formData.asset_type === 'manufacturing' && (
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Location"
                  name="location"
                  value={formData.location}
                  onChange={handleFormChange}
                />
              </Grid>
            )}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">
            {selectedAsset ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// Add missing import
const LinearProgress = ({ value, color, sx }) => (
  <Box sx={{ ...sx, bgcolor: 'rgba(255, 255, 255, 0.1)', borderRadius: 4 }}>
    <Box
      sx={{
        width: `${value}%`,
        height: '100%',
        bgcolor: color === 'success' ? '#4caf50' : color === 'warning' ? '#ff9800' : '#f44336',
        borderRadius: 4,
      }}
    />
  </Box>
);

export default Assets;
