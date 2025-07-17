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
} from 'react-native';

// Only import expo-document-picker if not on web, to avoid web-specific issues
const DocumentPicker = Platform.OS !== 'web' ? require('expo-document-picker') : null;

function App(): React.JSX.Element {
  const backgroundStyle = {
    backgroundColor: '#F3F3F3', // Light gray background for consistency
  };

  const [selectedFiles, setSelectedFiles] = useState<any[]>([]); // Use 'any' for flexibility with web FileList
  const [filingStatus, setFilingStatus] = useState<string>('');
  const [numDependents, setNumDependents] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [responseMessage, setResponseMessage] = useState<string>('');
  const [generatedFormLink, setGeneratedFormLink] = useState<string | null>(null); // State for the download link

  const fileInputRef = useRef<HTMLInputElement>(null); // Ref for web file input

  const pickDocuments = async () => {
    if (Platform.OS === 'web') {
      // For web, programmatically click the hidden input
      if (fileInputRef.current) {
        fileInputRef.current.click();
      }
      return;
    }

    // For mobile (iOS/Android) using expo-document-picker
    try {
      if (DocumentPicker) { // Ensure DocumentPicker is loaded
        const result = await DocumentPicker.getMultipleDocsAsync({
          type: 'application/pdf', // Use the MIME type string directly
        });

        if (result.canceled) {
          console.log('User cancelled document selection');
          setResponseMessage('Document selection cancelled.');
        } else {
          setSelectedFiles(result.assets || []);
          setResponseMessage(`Selected ${result.assets?.length || 0} file(s).`);
        }
      }
    } catch (err) {
      console.error('DocumentPicker Error:', err);
      Alert.alert('Error', 'Failed to pick documents.');
      setResponseMessage('Error picking documents.');
    }
  };

  // Handler for web file input change
  const handleWebFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const filesArray = Array.from(event.target.files).map(file => ({
        uri: URL.createObjectURL(file), // Create a blob URL for preview if needed
        name: file.name,
        type: file.type,
        size: file.size,
        fileObject: file, // Store the actual File object for FormData
      }));
      setSelectedFiles(filesArray);
      setResponseMessage(`Selected ${filesArray.length} file(s).`);
    }
  };

  const processDocuments = async () => {
    if (!selectedFiles || selectedFiles.length === 0) {
      Alert.alert('Validation Error', 'Please select at least one PDF tax document.');
      return;
    }
    if (!filingStatus.trim()) {
      Alert.alert('Validation Error', 'Please enter your filing status (e.g., Single, MFJ).');
      return;
    }
    if (!numDependents.trim() || isNaN(parseInt(numDependents, 10))) {
        Alert.alert('Validation Error', 'Please enter a valid number of dependents.');
        return;
    }

    setIsLoading(true);
    setResponseMessage('Processing documents...');
    setGeneratedFormLink(null); // Clear previous link

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      if (file) {
        // For web, use the actual File object stored in file.fileObject
        // For mobile, use the uri and name properties
        if (Platform.OS === 'web' && file.fileObject) {
          formData.append('files', file.fileObject);
        } else {
          formData.append('files', {
            uri: file.uri,
            name: file.name,
            type: file.type || 'application/pdf',
          } as any);
        }
      }
    });

    formData.append('filing_status', filingStatus);
    formData.append('num_dependents', numDependents);

    try {
      const backendUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000/upload-tax-documents/' : 'http://localhost:8000/upload-tax-documents/';
      
      const response = await fetch(backendUrl, {
        method: 'POST',
        body: formData,
        // 'Content-Type': 'multipart/form-data' is usually automatically set by fetch when using FormData
        // but it's good to be explicit for debugging if issues arise.
      });

      const data = await response.json();
      if (response.ok) {
        let success_msg = `Success! ${data.message}`;
        if (data.tax_summary) {
          // Corrected JavaScript formatting for numbers
          success_msg += `\nGross Income: $${data.tax_summary.gross_income.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          success_msg += `\nTaxable Income: $${data.tax_summary.taxable_income.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          success_msg += `\nCalculated Tax: $${data.tax_summary.calculated_tax.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          success_msg += `\nTotal Withheld: $${data.tax_summary.total_federal_withheld.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

          if (data.tax_summary.tax_due_or_refund < 0) {
              success_msg += `\nRefund: $${Math.abs(data.tax_summary.tax_due_or_refund).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          } else {
              success_msg += `\nTax Due: $${data.tax_summary.tax_due_or_refund.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          }
        }
        setResponseMessage(success_msg);
        Alert.alert('Success', success_msg);


        // Store the download link if provided by backend
        if (data.form_1040_download_link) {
            setGeneratedFormLink(data.form_1040_download_link);
        }

      } else {
        setResponseMessage(`Error: ${data.detail || 'Unknown error'}`);
        Alert.alert('Error', `Failed to process documents: ${data.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Network or processing error:', error);
      Alert.alert('Network Error', 'Could not connect to the backend or process documents.');
      setResponseMessage('Network or processing error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SafeAreaView style={[backgroundStyle, styles.container]}>
      <StatusBar />
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
        style={backgroundStyle}>
        <View style={styles.sectionContainer}>
          <Text style={styles.sectionTitle}>AI Tax Return Agent</Text>
          <Text style={styles.sectionDescription}>
            Upload your W-2, 1099-INT, and 1099-NEC PDFs.
          </Text>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Filing Status (e.g., Single, MFJ):</Text>
            <TextInput
              style={styles.input}
              onChangeText={setFilingStatus}
              value={filingStatus}
              placeholder="e.g., Single"
              autoCapitalize="words"
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Number of Dependents:</Text>
            <TextInput
              style={styles.input}
              onChangeText={setNumDependents}
              value={numDependents}
              placeholder="e.g., 0"
              keyboardType="numeric"
            />
          </View>

          {/* Conditional rendering for file input */}
          {Platform.OS === 'web' ? (
            <View>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleWebFileChange}
                style={{ display: 'none' }} // Hide the default input
                multiple
                accept="application/pdf"
              />
              <Button title="Select Tax Documents (PDFs)" onPress={pickDocuments} disabled={isLoading} />
            </View>
          ) : (
            <Button title="Select Tax Documents (PDFs)" onPress={pickDocuments} disabled={isLoading} />
          )}

          {selectedFiles && selectedFiles.length > 0 && (
            <Text style={styles.selectedFilesText}>
              Selected files: {selectedFiles.map(f => f?.name).filter(Boolean).join(', ')}
            </Text>
          )}

          <View style={styles.buttonSpacing} />

          <Button
            title={isLoading ? "Processing..." : "Process Tax Documents"}
            onPress={processDocuments}
            disabled={isLoading || !selectedFiles || selectedFiles.length === 0 || !filingStatus.trim() || !numDependents.trim()}
            color="#4CAF50" // Green for "Process"
          />

          {isLoading && <ActivityIndicator size="large" color="#0000ff" style={styles.loadingIndicator} />}

          {responseMessage ? (
            <Text style={styles.responseMessage}>{responseMessage}</Text>
          ) : null}

          {generatedFormLink ? (
            <View style={styles.downloadSection}>
              <Text style={styles.downloadText}>Your Form 1040 is ready:</Text>
              <Button title="Download Form 1040" onPress={() => window.open(`http://localhost:8000${generatedFormLink}`, '_blank')} />
              {/* Note: For mobile, window.open might open in external browser. Consider using Linking from react-native */}
            </View>
          ) : null}

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
  },
  sectionContainer: {
    marginTop: 32,
    paddingHorizontal: 24,
  },
  sectionTitle: {
    fontSize: 24,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
    textAlign: 'center',
  },
  sectionDescription: {
    marginTop: 8,
    fontSize: 18,
    fontWeight: '400',
    color: '#666',
    marginBottom: 24,
    textAlign: 'center',
  },
  inputGroup: {
    marginBottom: 15,
  },
  label: {
    fontSize: 16,
    marginBottom: 5,
    color: '#333',
  },
  input: {
    height: 40,
    borderColor: 'gray',
    borderWidth: 1,
    paddingHorizontal: 10,
    borderRadius: 5,
    color: '#333',
  },
  selectedFilesText: {
    marginTop: 10,
    fontSize: 14,
    color: '#666',
  },
  buttonSpacing: {
    height: 20,
  },
  loadingIndicator: {
    marginTop: 20,
  },
  responseMessage: {
    marginTop: 20,
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
  },
  downloadSection: {
    marginTop: 30,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#ccc',
    alignItems: 'center',
  },
  downloadText: {
    fontSize: 16,
    marginBottom: 10,
    color: '#333',
  }
});

export default App;
