import React, { useState, useRef } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
  Button,
  TextInput,
  Alert,
  ActivityIndicator,
  Platform,
  TouchableOpacity,
} from 'react-native';

// Only import expo-document-picker if not on web, to avoid web-specific issues
const DocumentPicker = Platform.OS !== 'web' ? require('expo-document-picker') : null;

// A simple card component for displaying extracted data
const InfoCard = ({ title, data }) => (
  <View style={styles.card}>
    <Text style={styles.cardTitle}>{title}</Text>
    {Object.entries(data).map(([key, value]) => (
      <View style={styles.cardRow} key={key}>
        <Text style={styles.cardKey}>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</Text>
        <Text style={styles.cardValue}>${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</Text>
      </View>
    ))}
  </View>
);

function App(): React.JSX.Element {
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [filingStatus, setFilingStatus] = useState<string>('Single');
  const [numDependents, setNumDependents] = useState<string>('0');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [responseMessage, setResponseMessage] = useState<string>('');
  const [taxSummary, setTaxSummary] = useState<any>(null);
  const [processedSummary, setProcessedSummary] = useState<any[]>([]);
  const [generatedFormLink, setGeneratedFormLink] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const pickDocuments = async () => {
    if (Platform.OS === 'web') {
      fileInputRef.current?.click();
      return;
    }
    try {
      if (DocumentPicker) {
        const result = await DocumentPicker.getMultipleDocsAsync({ type: 'application/pdf' });
        if (!result.canceled) {
          setSelectedFiles(result.assets || []);
        }
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to pick documents.');
    }
  };

  const handleWebFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const filesArray = Array.from(event.target.files).map(file => ({
        uri: URL.createObjectURL(file),
        name: file.name,
        type: file.type,
        size: file.size,
        fileObject: file,
      }));
      setSelectedFiles(filesArray);
    }
  };

  const processDocuments = async () => {
    if (selectedFiles.length === 0) {
      Alert.alert('Validation Error', 'Please select at least one PDF tax document.');
      return;
    }
    if (!filingStatus.trim() || !numDependents.trim()) {
      Alert.alert('Validation Error', 'Please complete all personal information fields.');
      return;
    }

    setIsLoading(true);
    setResponseMessage('AI is analyzing your documents... this may take a moment.');
    setTaxSummary(null);
    setProcessedSummary([]);
    setGeneratedFormLink(null);

    const formData = new FormData();
    selectedFiles.forEach(file => {
      formData.append('files', Platform.OS === 'web' ? file.fileObject : { uri: file.uri, name: file.name, type: 'application/pdf' } as any);
    });
    formData.append('filing_status', filingStatus);
    formData.append('num_dependents', numDependents);

    try {
      const backendUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000/upload-tax-documents/' : 'http://localhost:8000/upload-tax-documents/';
      const response = await fetch(backendUrl, { method: 'POST', body: formData });
      const data = await response.json();

      if (response.ok) {
        setResponseMessage(data.message);
        setTaxSummary(data.tax_summary);
        setProcessedSummary(data.processed_files_summary || []);
        if (data.form_1040_download_link) {
          setGeneratedFormLink(data.form_1040_download_link);
        }
      } else {
        setResponseMessage(`Error: ${data.detail || 'Unknown error'}`);
        Alert.alert('Error', `Failed to process documents: ${data.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Network or processing error:', error);
      Alert.alert('Network Error', 'Could not connect to the backend.');
      setResponseMessage('Network or processing error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <ScrollView contentInsetAdjustmentBehavior="automatic" style={styles.scrollView}>
        <View style={styles.container}>
          <Text style={styles.headerTitle}>AI Tax Agent</Text>
          <Text style={styles.headerSubtitle}>Upload your tax forms to automatically calculate your return.</Text>

          <View style={styles.inputSection}>
            <Text style={styles.label}>Filing Status</Text>
            <TextInput style={styles.input} onChangeText={setFilingStatus} value={filingStatus} placeholder="e.g., Single" />
            <Text style={styles.label}>Number of Dependents</Text>
            <TextInput style={styles.input} onChangeText={setNumDependents} value={numDependents} placeholder="e.g., 0" keyboardType="numeric" />
          </View>

          {Platform.OS === 'web' && (
            <input type="file" ref={fileInputRef} onChange={handleWebFileChange} style={{ display: 'none' }} multiple accept="application/pdf" />
          )}
          <TouchableOpacity style={styles.button} onPress={pickDocuments} disabled={isLoading}>
            <Text style={styles.buttonText}>Select Documents</Text>
          </TouchableOpacity>

          {selectedFiles.length > 0 && (
            <Text style={styles.selectedFilesText}>
              {selectedFiles.length} file(s) selected: {selectedFiles.map(f => f.name).join(', ')}
            </Text>
          )}

          <TouchableOpacity style={[styles.button, styles.processButton]} onPress={processDocuments} disabled={isLoading || selectedFiles.length === 0}>
            <Text style={styles.buttonText}>{isLoading ? "Processing..." : "Calculate Tax Return"}</Text>
          </TouchableOpacity>

          {isLoading && <ActivityIndicator size="large" color="#007AFF" style={styles.loadingIndicator} />}
          {responseMessage && !isLoading && <Text style={styles.responseMessage}>{responseMessage}</Text>}

          {taxSummary && (
            <View style={styles.resultsSection}>
              <Text style={styles.resultsTitle}>Tax Calculation Summary</Text>
              <InfoCard title="Final Calculation" data={taxSummary} />

              <Text style={styles.resultsTitle}>Extracted Data from Documents</Text>
              {processedSummary.length > 0 ? (
                processedSummary.map((item, index) => (
                  <InfoCard key={index} title={`Form: ${item.form_type}`} data={item.fields} />
                ))
              ) : (
                <Text>No data was extracted from the documents.</Text>
              )}

              {generatedFormLink && (
                <TouchableOpacity style={[styles.button, styles.downloadButton]} onPress={() => window.open(`http://localhost:8000${generatedFormLink}`, '_blank')}>
                  <Text style={styles.buttonText}>Download Form 1040 PDF</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F0F4F8' },
  scrollView: { backgroundColor: '#F0F4F8' },
  container: { padding: 20 },
  headerTitle: { fontSize: 32, fontWeight: 'bold', color: '#1A202C', textAlign: 'center' },
  headerSubtitle: { fontSize: 16, color: '#4A5568', textAlign: 'center', marginBottom: 30 },
  inputSection: { marginBottom: 20 },
  label: { fontSize: 16, color: '#2D3748', marginBottom: 8 },
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#CBD5E0',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: '#1A202C',
    marginBottom: 15,
  },
  button: {
    backgroundColor: '#4299E1',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 15,
  },
  processButton: { backgroundColor: '#48BB78' },
  downloadButton: { backgroundColor: '#A0AEC0', marginTop: 20 },
  buttonText: { color: '#FFFFFF', fontSize: 16, fontWeight: 'bold' },
  selectedFilesText: { textAlign: 'center', color: '#4A5568', marginBottom: 20, fontStyle: 'italic' },
  loadingIndicator: { marginVertical: 20 },
  responseMessage: { textAlign: 'center', color: '#2D3748', fontSize: 16, marginVertical: 10 },
  resultsSection: { marginTop: 30, borderTopWidth: 1, borderTopColor: '#E2E8F0', paddingTop: 20 },
  resultsTitle: { fontSize: 22, fontWeight: 'bold', color: '#1A202C', marginBottom: 15 },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 15,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  cardTitle: { fontSize: 18, fontWeight: 'bold', color: '#2D3748', marginBottom: 10, borderBottomWidth: 1, borderBottomColor: '#E2E8F0', paddingBottom: 5 },
  cardRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 5 },
  cardKey: { fontSize: 16, color: '#4A5568' },
  cardValue: { fontSize: 16, color: '#1A202C', fontWeight: '500' },
});

export default App;
