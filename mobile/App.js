import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, Alert, Dimensions, Platform, Modal } from 'react-native';
import { Card, Button } from 'react-native-paper';
import { LineChart } from 'react-native-chart-kit';
import axios from 'axios';

// Storage için platform-specific import
const getStorage = () => {
  if (Platform.OS === 'web') {
    return {
      getItem: (key) => Promise.resolve(localStorage.getItem(key)),
      setItem: (key, value) => Promise.resolve(localStorage.setItem(key, value)),
    };
  }
  // React Native için AsyncStorage (eğer yüklüyse)
  try {
    const AsyncStorage = require('@react-native-async-storage/async-storage').default;
    return AsyncStorage;
  } catch {
    // Fallback: web için localStorage
    return {
      getItem: (key) => Promise.resolve(localStorage.getItem(key)),
      setItem: (key, value) => Promise.resolve(localStorage.setItem(key, value)),
    };
  }
};

const storage = getStorage();

// Platform'a göre API URL'i ayarla
const getApiUrl = () => {
  if (__DEV__) {
    if (Platform.OS === 'android') {
      return 'http://10.0.2.2:8000/api';  // Android emulator
    } else if (Platform.OS === 'web') {
      return 'http://localhost:8000/api';  // Web browser
    } else {
      return 'http://localhost:8000/api';  // iOS simulator
    }
  }
  return 'https://your-api-domain.com/api';  // Production
};

const API_BASE_URL = getApiUrl();

export default function App() {
  const [stats, setStats] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analysisModalVisible, setAnalysisModalVisible] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    // Load theme preference
    const loadTheme = async () => {
      try {
        const savedTheme = await storage.getItem('theme') || 'light';
        setIsDarkMode(savedTheme === 'dark');
      } catch (error) {
        console.error('Theme yükleme hatası:', error);
      }
    };
    
    loadTheme();
    
    const fetchData = async () => {
      setLoading(true);
      await Promise.all([loadDashboard(), loadFiles()]);
      setLoading(false);
    };
    fetchData();
  }, []);

  const toggleTheme = async () => {
    const newTheme = !isDarkMode;
    setIsDarkMode(newTheme);
    try {
      await storage.setItem('theme', newTheme ? 'dark' : 'light');
    } catch (error) {
      console.error('Theme kaydetme hatası:', error);
    }
  };

  const loadDashboard = async () => {
    try {
      console.log('API URL:', API_BASE_URL);
      const response = await axios.get(`${API_BASE_URL}/dashboard/stats`);
      console.log('Dashboard response:', response.data);
      setStats(response.data);
      console.log('Stats state set edildi:', response.data);
    } catch (error) {
      console.error('Dashboard yükleme hatası:', error);
      console.error('Error details:', error.message);
      if (error.response) {
        console.error('Response status:', error.response.status);
        console.error('Response data:', error.response.data);
      }
    }
  };

  const loadFiles = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/logs/`);
      console.log('Files response:', response.data);
      setFiles(response.data);
      console.log('Files state set edildi, toplam:', response.data.length, 'dosya');
    } catch (error) {
      console.error('Dosya yükleme hatası:', error);
      console.error('Error details:', error.message);
      if (error.response) {
        console.error('Response status:', error.response.status);
        console.error('Response data:', error.response.data);
      }
    }
  };

  const loadAnalysis = async (fileId) => {
    setLoadingAnalysis(true);
    try {
      console.log('Analiz yükleniyor, file ID:', fileId);
      const response = await axios.get(`${API_BASE_URL}/analysis/${fileId}`);
      console.log('Analysis response:', response.data);
      setSelectedAnalysis(response.data);
      setAnalysisModalVisible(true);
    } catch (error) {
      console.error('Analiz yükleme hatası:', error);
      Alert.alert('Hata', 'Analiz yüklenirken bir hata oluştu: ' + (error.message || 'Bilinmeyen hata'));
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const chartConfig = {
    backgroundColor: '#ffffff',
    backgroundGradientFrom: '#ffffff',
    backgroundGradientTo: '#ffffff',
    color: (opacity = 1) => `rgba(102, 126, 234, ${opacity})`,
    strokeWidth: 2,
  };

  const screenWidth = Dimensions.get('window').width;

  const getThemeStyles = (dark) => {
    if (dark) {
      return {
        container: { backgroundColor: '#1a1a2e' },
        header: { backgroundColor: '#16213e' },
        card: { backgroundColor: '#252538' },
        text: { color: '#e0e0e0' },
        textSecondary: { color: '#b0b0b0' },
        modalOverlay: { backgroundColor: 'rgba(0, 0, 0, 0.7)' },
        modalContent: { backgroundColor: '#1e1e2e' },
      };
    }
    return {
      container: { backgroundColor: '#f5f5f5' },
      header: { backgroundColor: '#667eea' },
      card: { backgroundColor: '#ffffff' },
      text: { color: '#333' },
      textSecondary: { color: '#666' },
      modalOverlay: { backgroundColor: 'rgba(0, 0, 0, 0.5)' },
      modalContent: { backgroundColor: '#ffffff' },
    };
  };

  const themeStyles = getThemeStyles(isDarkMode);

  return (
    <ScrollView style={[styles.container, themeStyles.container]}>
      <View style={[styles.header, themeStyles.header]}>
        <Button
          mode="text"
          onPress={toggleTheme}
          style={styles.themeButton}
          labelStyle={styles.themeButtonLabel}
        >
          {isDarkMode ? '☀️' : '🌙'}
        </Button>
        <Text style={styles.title}>🔍 Log Analyzer</Text>
        <Text style={styles.subtitle}>Akıllı Log Analiz Sistemi</Text>
      </View>

      {loading && !stats && (
        <View style={styles.statsContainer}>
          <Text style={styles.loadingText}>İstatistikler yükleniyor...</Text>
        </View>
      )}

      {stats ? (
        <View style={styles.statsContainer}>
          <Card style={[styles.card, themeStyles.card]}>
            <Card.Content>
              <Text style={[styles.cardTitle, themeStyles.text]}>İstatistikler</Text>
              <View style={styles.statRow}>
                <Text style={[styles.statLabel, themeStyles.textSecondary]}>Toplam Dosya:</Text>
                <Text style={[styles.statValue, themeStyles.text]}>{stats.total_files || 0}</Text>
              </View>
              <View style={styles.statRow}>
                <Text style={[styles.statLabel, themeStyles.textSecondary]}>Toplam Giriş:</Text>
                <Text style={[styles.statValue, themeStyles.text]}>{(stats.total_entries || 0).toLocaleString()}</Text>
              </View>
              <View style={styles.statRow}>
                <Text style={[styles.statLabel, themeStyles.textSecondary]}>Toplam Hata:</Text>
                <Text style={[styles.statValue, themeStyles.text]}>{(stats.total_errors || 0).toLocaleString()}</Text>
              </View>
              <View style={styles.statRow}>
                <Text style={[styles.statLabel, themeStyles.textSecondary]}>Toplam Uyarı:</Text>
                <Text style={[styles.statValue, themeStyles.text]}>{(stats.total_warnings || 0).toLocaleString()}</Text>
              </View>
            </Card.Content>
          </Card>

          {stats.error_trend && stats.error_trend.length > 0 && (
            <Card style={[styles.card, themeStyles.card]}>
              <Card.Content>
                <Text style={[styles.cardTitle, themeStyles.text]}>Hata Trendi</Text>
                <LineChart
                  data={{
                    labels: stats.error_trend.slice(0, 7).map(t => t.filename.substring(0, 10)),
                    datasets: [{
                      data: stats.error_trend.slice(0, 7).map(t => t.error_count)
                    }]
                  }}
                  width={screenWidth - 40}
                  height={220}
                  chartConfig={chartConfig}
                  bezier
                  style={styles.chart}
                />
              </Card.Content>
            </Card>
          )}
        </View>
      ) : !loading && (
        <View style={styles.statsContainer}>
          <Text style={styles.emptyText}>İstatistikler yüklenemedi</Text>
        </View>
      )}

      <View style={styles.filesContainer}>
        <Text style={[styles.sectionTitle, themeStyles.text]}>Yüklenen Dosyalar</Text>
        {loading ? (
          <Text style={styles.loadingText}>Yükleniyor...</Text>
        ) : files.length === 0 ? (
          <Text style={styles.emptyText}>Henüz dosya yüklenmemiş</Text>
        ) : (
          <>
            {files.slice(0, 5).map((file) => (
              <Card key={file.id} style={[styles.fileCard, themeStyles.card]}>
                <Card.Content>
                  <Text style={[styles.fileName, themeStyles.text]}>{file.filename}</Text>
                  <Text style={[styles.fileInfo, themeStyles.textSecondary]}>
                    {file.total_lines} satır • {new Date(file.uploaded_at).toLocaleDateString('tr-TR')} {new Date(file.uploaded_at).toLocaleTimeString('tr-TR')}
                  </Text>
                  <Text style={[styles.fileInfo, themeStyles.textSecondary]}>
                    Durum: {file.status || 'completed'}
                  </Text>
                  <Button
                    mode="contained"
                    onPress={() => loadAnalysis(file.id)}
                    style={styles.analyzeButton}
                    loading={loadingAnalysis}
                    disabled={loadingAnalysis}
                  >
                    {loadingAnalysis ? 'Yükleniyor...' : 'Analiz'}
                  </Button>
                </Card.Content>
              </Card>
            ))}
            {files.length > 5 && (
              <Text style={styles.moreText}>... ve {files.length - 5} dosya daha</Text>
            )}
          </>
        )}
      </View>

      {/* Analiz Detay Modal */}
      <Modal
        visible={analysisModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setAnalysisModalVisible(false)}
      >
        <View style={[styles.modalOverlay, themeStyles.modalOverlay]}>
          <View style={[styles.modalContent, themeStyles.modalContent]}>
            <ScrollView>
              <View style={styles.modalHeader}>
                <Text style={[styles.modalTitle, themeStyles.text]}>📊 Analiz Detayları</Text>
                <Button
                  mode="text"
                  onPress={() => setAnalysisModalVisible(false)}
                  style={styles.closeButton}
                >
                  ✕ Kapat
                </Button>
              </View>

              {selectedAnalysis && (
                <>
                  <Card style={[styles.card, themeStyles.card]}>
                    <Card.Content>
                      <Text style={[styles.cardTitle, themeStyles.text]}>Genel İstatistikler</Text>
                      <View style={styles.statRow}>
                        <Text style={styles.statLabel}>Toplam Giriş:</Text>
                        <Text style={styles.statValue}>{selectedAnalysis.total_entries || 0}</Text>
                      </View>
                      <View style={styles.statRow}>
                        <Text style={styles.statLabel}>Hata Sayısı:</Text>
                        <Text style={[styles.statValue, {color: '#e74c3c'}]}>{selectedAnalysis.error_count || 0}</Text>
                      </View>
                      <View style={styles.statRow}>
                        <Text style={styles.statLabel}>Uyarı Sayısı:</Text>
                        <Text style={[styles.statValue, {color: '#f39c12'}]}>{selectedAnalysis.warning_count || 0}</Text>
                      </View>
                      <View style={styles.statRow}>
                        <Text style={styles.statLabel}>Bilgi Sayısı:</Text>
                        <Text style={[styles.statValue, {color: '#3498db'}]}>{selectedAnalysis.info_count || 0}</Text>
                      </View>
                      <View style={styles.statRow}>
                        <Text style={styles.statLabel}>Debug Sayısı:</Text>
                        <Text style={[styles.statValue, {color: '#95a5a6'}]}>{selectedAnalysis.debug_count || 0}</Text>
                      </View>
                    </Card.Content>
                  </Card>

                  {selectedAnalysis.top_errors && selectedAnalysis.top_errors.length > 0 && (
                    <Card style={[styles.card, themeStyles.card]}>
                      <Card.Content>
                        <Text style={[styles.cardTitle, themeStyles.text]}>🔴 En Sık Tekrar Eden Hatalar</Text>
                        {selectedAnalysis.top_errors.slice(0, 5).map((error, index) => (
                          <View key={index} style={styles.errorItem}>
                            <Text style={styles.errorText}>
                              {index + 1}. {error.message || error}
                            </Text>
                            {error.count && (
                              <Text style={styles.errorCount}>{error.count} kez</Text>
                            )}
                          </View>
                        ))}
                      </Card.Content>
                    </Card>
                  )}

                  {selectedAnalysis.top_warnings && selectedAnalysis.top_warnings.length > 0 && (
                    <Card style={[styles.card, themeStyles.card]}>
                      <Card.Content>
                        <Text style={[styles.cardTitle, themeStyles.text]}>⚠️ En Sık Tekrar Eden Uyarılar</Text>
                        {selectedAnalysis.top_warnings.slice(0, 5).map((warning, index) => (
                          <View key={index} style={styles.errorItem}>
                            <Text style={styles.errorText}>
                              {index + 1}. {warning.message || warning}
                            </Text>
                            {warning.count && (
                              <Text style={styles.errorCount}>{warning.count} kez</Text>
                            )}
                          </View>
                        ))}
                      </Card.Content>
                    </Card>
                  )}

                  {selectedAnalysis.ai_comment && (
                    <Card style={[styles.card, themeStyles.card]}>
                      <Card.Content>
                        <Text style={[styles.cardTitle, themeStyles.text]}>🤖 AI Yorumu</Text>
                        <Text style={[styles.aiText, themeStyles.textSecondary]}>{selectedAnalysis.ai_comment}</Text>
                      </Card.Content>
                    </Card>
                  )}

                  {selectedAnalysis.ai_suggestions && selectedAnalysis.ai_suggestions.length > 0 && (
                    <Card style={[styles.card, themeStyles.card]}>
                      <Card.Content>
                        <Text style={[styles.cardTitle, themeStyles.text]}>💡 AI Önerileri</Text>
                        {selectedAnalysis.ai_suggestions.map((suggestion, index) => (
                          <Text key={index} style={[styles.suggestionText, themeStyles.textSecondary]}>
                            • {suggestion}
                          </Text>
                        ))}
                      </Card.Content>
                    </Card>
                  )}

                  {selectedAnalysis.analyzed_at && (
                    <Text style={styles.analyzedAt}>
                      Analiz Tarihi: {new Date(selectedAnalysis.analyzed_at).toLocaleString('tr-TR')}
                    </Text>
                  )}
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#667eea',
    padding: 20,
    paddingTop: 50,
    alignItems: 'center',
    position: 'relative',
  },
  themeButton: {
    position: 'absolute',
    top: 10,
    right: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
  },
  themeButtonLabel: {
    fontSize: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#ffffff',
    marginBottom: 5,
  },
  subtitle: {
    fontSize: 14,
    color: '#ffffff',
    opacity: 0.9,
  },
  statsContainer: {
    padding: 20,
  },
  card: {
    marginBottom: 15,
    elevation: 3,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 15,
    color: '#333',
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  statLabel: {
    fontSize: 14,
    color: '#666',
  },
  statValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#667eea',
  },
  chart: {
    marginVertical: 8,
    borderRadius: 16,
  },
  filesContainer: {
    padding: 20,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 15,
    color: '#333',
  },
  fileCard: {
    marginBottom: 15,
    elevation: 2,
  },
  fileName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 5,
  },
  fileInfo: {
    fontSize: 12,
    color: '#666',
    marginBottom: 10,
  },
  analyzeButton: {
    marginTop: 10,
    backgroundColor: '#667eea',
  },
  loadingText: {
    textAlign: 'center',
    padding: 20,
    color: '#666',
  },
  emptyText: {
    textAlign: 'center',
    padding: 20,
    color: '#999',
    fontStyle: 'italic',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#ffffff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
    padding: 20,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    paddingBottom: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#333',
  },
  closeButton: {
    marginTop: -10,
  },
  errorItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  errorText: {
    flex: 1,
    fontSize: 13,
    color: '#333',
    marginRight: 10,
  },
  errorCount: {
    fontSize: 12,
    color: '#667eea',
    fontWeight: 'bold',
  },
  aiText: {
    fontSize: 14,
    color: '#555',
    lineHeight: 20,
    marginTop: 10,
  },
  suggestionText: {
    fontSize: 13,
    color: '#555',
    lineHeight: 20,
    marginTop: 8,
  },
  analyzedAt: {
    fontSize: 11,
    color: '#999',
    textAlign: 'center',
    marginTop: 15,
    marginBottom: 20,
    fontStyle: 'italic',
  },
});

