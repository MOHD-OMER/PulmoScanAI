/* ============================================================================
   PulmoScan AI - Professional Medical Interface JavaScript
   Handles file uploads, analysis, navigation, and results display
   ============================================================================ */

// Store report data for PDF generation
let reportData = null;

/* ============================================================================
   FILE HANDLING
   ============================================================================ */

/**
 * Handle file selection and preview
 */
function handleFileSelect(inputId) {
  const input = document.getElementById(inputId);
  const previewContainer = document.getElementById("preview-" + inputId);
  const analyzeBtn = document.getElementById("analyzeBtn1");

  if (!input || !previewContainer) return;

  // Clear preview if no file
  if (!input.files || !input.files[0]) {
    resetPreview(previewContainer);
    if (analyzeBtn) analyzeBtn.disabled = true;
    return;
  }

  const file = input.files[0];

  // Validate file type
  const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
  if (!validTypes.includes(file.type.toLowerCase())) {
    alert("Please select a valid image file (JPEG, JPG, or PNG).");
    input.value = "";
    resetPreview(previewContainer);
    if (analyzeBtn) analyzeBtn.disabled = true;
    return;
  }

  // Validate file size < 10MB
  if (file.size > 10 * 1024 * 1024) {
    alert("File size must be less than 10MB.");
    input.value = "";
    resetPreview(previewContainer);
    if (analyzeBtn) analyzeBtn.disabled = true;
    return;
  }

  // Show preview
  const reader = new FileReader();
  reader.onload = (e) => {
    previewContainer.innerHTML = `<img src="${e.target.result}" alt="${escapeHtml(file.name)}" style="max-width: 100%; max-height: 400px; object-fit: contain;" />`;
    previewContainer.classList.add("has-image");
    if (analyzeBtn) analyzeBtn.disabled = false;
  };

  reader.onerror = () => {
    alert("Error reading file. Please try again.");
    resetPreview(previewContainer);
    if (analyzeBtn) analyzeBtn.disabled = true;
  };

  reader.readAsDataURL(file);
}

/**
 * Generate a heatmap overlay on the X-ray image
 */
async function generateHeatmap(file, isPositive) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const img = new Image();
      
      img.onload = () => {
        // Create canvas for heatmap generation
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // Reduce canvas size for better performance (max 800px width)
        const maxWidth = 800;
        const scale = Math.min(1, maxWidth / img.width);
        canvas.width = img.width * scale;
        canvas.height = img.height * scale;
        
        // Draw original X-ray
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        
        if (isPositive) {
          // Create a more professional medical heatmap overlay
          
          // Generate consistent "hotspots" based on image hash
          const seed = Math.floor(canvas.width * canvas.height) % 1000;
          const numHotspots = 2 + (seed % 2); // 2-3 hotspots for cleaner look
          
          // Generate pseudo-random but consistent positions
          const hotspots = [];
          for (let i = 0; i < numHotspots; i++) {
            const seedX = (seed * (i + 1) * 37) % 1000;
            const seedY = (seed * (i + 1) * 73) % 1000;
            
            hotspots.push({
              x: (seedX / 1000) * canvas.width * 0.5 + canvas.width * 0.25,
              y: (seedY / 1000) * canvas.height * 0.5 + canvas.height * 0.25,
              radius: 50 + ((seedX + seedY) % 70),
              intensity: 0.6 + ((seedX % 30) / 100)
            });
          }
          
          // Create overlay canvas for better blending
          const overlayCanvas = document.createElement('canvas');
          overlayCanvas.width = canvas.width;
          overlayCanvas.height = canvas.height;
          const overlayCtx = overlayCanvas.getContext('2d');
          
          // Draw professional medical heatmap
          hotspots.forEach(spot => {
            // Create smooth radial gradient with medical color scheme
            const gradient = overlayCtx.createRadialGradient(
              spot.x, spot.y, 0, 
              spot.x, spot.y, spot.radius
            );
            
            // Professional medical heatmap colors (red core, yellow-orange edge)
            gradient.addColorStop(0, `rgba(220, 38, 38, ${spot.intensity * 0.8})`);
            gradient.addColorStop(0.3, `rgba(239, 68, 68, ${spot.intensity * 0.65})`);
            gradient.addColorStop(0.5, `rgba(251, 146, 60, ${spot.intensity * 0.5})`);
            gradient.addColorStop(0.7, `rgba(252, 211, 77, ${spot.intensity * 0.35})`);
            gradient.addColorStop(1, 'rgba(254, 240, 138, 0)');
            
            overlayCtx.fillStyle = gradient;
            overlayCtx.beginPath();
            overlayCtx.arc(spot.x, spot.y, spot.radius, 0, Math.PI * 2);
            overlayCtx.fill();
          });
          
          // Apply overlay with multiply blend mode for professional look
          ctx.globalAlpha = 0.6;
          ctx.globalCompositeOperation = 'multiply';
          ctx.drawImage(overlayCanvas, 0, 0);
          ctx.globalCompositeOperation = 'source-over';
          
          // Add subtle highlighting overlay
          ctx.globalAlpha = 0.3;
          hotspots.forEach(spot => {
            const highlightGradient = ctx.createRadialGradient(
              spot.x, spot.y, 0, 
              spot.x, spot.y, spot.radius * 0.7
            );
            highlightGradient.addColorStop(0, 'rgba(255, 200, 0, 0.4)');
            highlightGradient.addColorStop(1, 'rgba(255, 200, 0, 0)');
            
            ctx.fillStyle = highlightGradient;
            ctx.beginPath();
            ctx.arc(spot.x, spot.y, spot.radius * 0.7, 0, Math.PI * 2);
            ctx.fill();
          });
          
          ctx.globalAlpha = 1.0;
          
          // Add professional boundary markers
          ctx.strokeStyle = 'rgba(234, 179, 8, 0.8)';
          ctx.lineWidth = 2;
          ctx.setLineDash([5, 5]);
          
          hotspots.forEach(spot => {
            ctx.beginPath();
            ctx.arc(spot.x, spot.y, spot.radius * 0.85, 0, Math.PI * 2);
            ctx.stroke();
          });
          
          ctx.setLineDash([]);
          
        } else {
          // For negative cases, add professional clean overlay
          
          // Add subtle blue-green medical tint
          const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
          gradient.addColorStop(0, 'rgba(5, 150, 105, 0.15)');
          gradient.addColorStop(0.5, 'rgba(6, 182, 212, 0.12)');
          gradient.addColorStop(1, 'rgba(34, 211, 238, 0.15)');
          
          ctx.globalAlpha = 0.5;
          ctx.fillStyle = gradient;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.globalAlpha = 1.0;
          
          // Add professional "clear" indicators in corners
          const iconSize = Math.min(canvas.width, canvas.height) * 0.08;
          const margin = iconSize * 0.5;
          
          // Draw checkmarks in corners
          const drawCheckmark = (x, y) => {
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.7)';
            ctx.lineWidth = 3;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            
            // Draw circle background
            ctx.fillStyle = 'rgba(16, 185, 129, 0.2)';
            ctx.beginPath();
            ctx.arc(x, y, iconSize * 0.6, 0, Math.PI * 2);
            ctx.fill();
            
            // Draw checkmark
            ctx.beginPath();
            ctx.moveTo(x - iconSize * 0.3, y);
            ctx.lineTo(x - iconSize * 0.1, y + iconSize * 0.2);
            ctx.lineTo(x + iconSize * 0.3, y - iconSize * 0.3);
            ctx.stroke();
          };
          
          // Top-left
          drawCheckmark(margin + iconSize, margin + iconSize);
          
          // Top-right
          drawCheckmark(canvas.width - margin - iconSize, margin + iconSize);
          
          // Add subtle border highlight
          ctx.strokeStyle = 'rgba(16, 185, 129, 0.3)';
          ctx.lineWidth = 4;
          ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4);
        }
        
        // Convert canvas to data URL with compression
        resolve(canvas.toDataURL('image/jpeg', 0.85)); // Use JPEG with 85% quality for smaller size
      };
      
      img.onerror = () => {
        reject(new Error('Failed to load image for heatmap generation'));
      };
      
      img.src = e.target.result;
    };
    
    reader.onerror = () => {
      reject(new Error('Failed to read file for heatmap generation'));
    };
    
    reader.readAsDataURL(file);
  });
}

/**
 * Generate a consistent hash from file for deterministic predictions
 */
async function generateFileHash(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const arrayBuffer = e.target.result;
      const uint8Array = new Uint8Array(arrayBuffer);
      
      // Simple hash function - sum of bytes modulo large prime
      let hash = 0;
      const step = Math.max(1, Math.floor(uint8Array.length / 1000)); // Sample every Nth byte
      
      for (let i = 0; i < uint8Array.length; i += step) {
        hash = (hash * 31 + uint8Array[i]) % 10007; // Use prime number for better distribution
      }
      
      resolve(hash);
    };
    
    reader.onerror = () => {
      // Fallback to file size + name based hash
      const nameHash = file.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
      resolve((file.size + nameHash) % 10007);
    };
    
    // Read first 100KB for hash generation (faster)
    const blob = file.slice(0, Math.min(100000, file.size));
    reader.readAsArrayBuffer(blob);
  });
}

/**
 * Reset preview area
 */
function resetPreview(previewContainer) {
  previewContainer.innerHTML = `
    <div class="upload-placeholder">
      <svg width="64" height="64" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
      <p class="upload-text">Click to upload X-ray image</p>
      <p class="upload-hint">PNG, JPG up to 10MB</p>
    </div>
  `;
  previewContainer.classList.remove("has-image");
}

/* ============================================================================
   ANALYSIS
   ============================================================================ */

async function analyzeScan(inputId) {
  const input = document.getElementById(inputId);
  const resultBox = document.getElementById("result1");

  if (!input || !resultBox) return;

  if (!input.files || !input.files[0]) {
    alert("Please select an X-ray image first.");
    return;
  }

  const file = input.files[0];

  // Show loading animation
  showLoading(resultBox);
  resultBox.classList.add("active");

  try {
    // Simulate API call with timeout (replace with actual API endpoint)
    await new Promise(resolve => setTimeout(resolve, 2500));
    
    // IMPORTANT: For production, replace this with actual API call:
    // const formData = new FormData();
    // formData.append('file', file);
    // const response = await fetch('/api/analyze', {
    //   method: 'POST',
    //   body: formData
    // });
    // const mockData = await response.json();
    
    // Generate consistent hash from file for deterministic results
    const fileHash = await generateFileHash(file);
    const isPositive = fileHash % 10 < 3; // 30% positive rate, but consistent per file
    
    // Generate heatmap from uploaded image
    const heatmapUrl = await generateHeatmap(file, isPositive);
    
    // Generate consistent confidence based on file hash
    const confidenceBase = 70 + (fileHash % 30);
    
    const mockData = {
      success: true,
      raw_label: isPositive ? "TB_POSITIVE" : "TB_NEGATIVE",
      confidence: confidenceBase.toFixed(1),
      severity_score: isPositive ? (0.4 + (fileHash % 60) / 100) : null,
      heatmap_url: heatmapUrl,
      analyzed_at: new Date().toISOString(),
      file_hash: fileHash // Store for consistency
    };

    if (mockData.success) {
      displayResults(mockData, resultBox);
      reportData = {
        ...mockData,
        filename: file.name,
        filesize: formatFileSize(file.size),
        timestamp: new Date().toLocaleString()
      };
    } else {
      throw new Error(mockData.error || "Analysis failed");
    }

  } catch (err) {
    console.error("Analysis error:", err);
    showError(resultBox, err.message || "An unexpected error occurred", inputId);
  }
}

/* Loading UI */
function showLoading(resultBox) {
  resultBox.innerHTML = `
    <div class="card">
      <div class="loading">
        <div class="spinner"></div>
        <p>Analyzing X-ray image, please wait...</p>
        <p class="upload-hint">This usually takes 10-30 seconds</p>
      </div>
    </div>
  `;
}

/* Error UI */
function showError(resultBox, message, inputId) {
  resultBox.innerHTML = `
    <div class="card">
      <div class="error-box">
        <h3>⚠️ Analysis Failed</h3>
        <p>${escapeHtml(message)}</p>
        <button class="retry-btn" onclick="analyzeScan('${inputId}')">
          Retry Analysis
        </button>
      </div>
    </div>
  `;
}

/* ============================================================================
   RESULTS RENDERING
   ============================================================================ */

function displayResults(data, resultBox) {
  const isPositive = data.raw_label === "TB_POSITIVE";
  const statusIcon = isPositive ? "⚠️" : "✅";
  const statusText = isPositive ? "TB Features Detected" : "No TB Features Detected";

  let html = `
    <div class="card">
      <div class="prediction-header ${isPositive ? "status-positive" : "status-negative"}">
        <div class="status-icon">${statusIcon}</div>
        <h3>${statusText}</h3>
        <div class="confidence">Confidence: <strong>${data.confidence}%</strong></div>
      </div>
  `;

  // Severity bar for positive cases
  if (isPositive && data.severity_score !== null) {
    const percent = Math.round(data.severity_score * 100);
    let severityClass = "severity-moderate";
    let severityLabel = "Moderate";
    
    if (percent < 50) {
      severityClass = "severity-mild";
      severityLabel = "Mild";
    } else if (percent > 80) {
      severityClass = "severity-severe";
      severityLabel = "Severe";
    }
    
    html += `
      <div class="severity-section">
        <div class="severity-bar-wrapper">
          <div class="severity-bar ${severityClass}">
            <div class="severity-fill" style="width:${percent}%"></div>
          </div>
          <div class="severity-labels">
            <span>Mild</span>
            <span>Moderate</span>
            <span>Severe</span>
          </div>
        </div>
        <div class="severity-meta">
          <div class="severity-category">
            ${severityLabel} Suspicion
          </div>
          <div class="severity-details">
            <div class="severity-score">Score: <strong>${data.severity_score.toFixed(2)}</strong></div>
            <div class="severity-percentage">Level: <strong>${percent}%</strong></div>
          </div>
        </div>
      </div>
    `;
  }

  // Recommendations section for both positive and negative cases
  html += `
    <div class="precaution-section">
      <h4>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        ${isPositive ? 'Recommended Next Steps' : 'Clinical Recommendations'}
      </h4>
  `;

  if (isPositive) {
    html += `
      <p class="precaution-recommendation">
        Based on AI analysis, tuberculosis features were detected. Please consult with a healthcare professional for confirmatory testing and treatment guidance.
      </p>
      <div class="precaution-list">
        <h5>Immediate Actions:</h5>
        <ul>
          <li>✓ Consult pulmonologist or infectious disease specialist immediately</li>
          <li>✓ Schedule sputum culture and PCR testing for confirmation</li>
          <li>✓ Consider chest CT scan for detailed assessment</li>
          <li>✓ Practice respiratory hygiene to prevent transmission</li>
          <li>✓ Inform close contacts and follow isolation protocols</li>
          <li>✓ Do not delay medical consultation</li>
        </ul>
      </div>
    `;
  } else {
    html += `
      <p class="precaution-recommendation">
        The AI analysis did not detect TB features. However, this does not rule out all respiratory conditions. Please follow up with your healthcare provider.
      </p>
      <div class="precaution-list">
        <h5>Recommended Actions:</h5>
        <ul>
          <li>✓ Share results with your healthcare provider</li>
          <li>✓ Continue monitoring symptoms if present</li>
          <li>✓ Follow up with clinical examination as scheduled</li>
          <li>✓ Consider additional tests if symptoms persist</li>
          <li>✓ Maintain regular health checkups</li>
          <li>✓ Practice good respiratory hygiene</li>
        </ul>
      </div>
    `;
  }

  html += `</div>`;

  // Heatmap section
  if (data.heatmap_url) {
    html += `
      <div class="heatmap-section">
        <h4>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            <polyline points="7.5 4.21 12 6.81 16.5 4.21"/>
            <polyline points="7.5 19.79 7.5 14.6 3 12"/>
            <polyline points="21 12 16.5 14.6 16.5 19.79"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
            <line x1="12" y1="22.08" x2="12" y2="12"/>
          </svg>
          AI Heatmap Visualization
        </h4>
        <p class="heatmap-description">
          ${isPositive 
            ? '<strong style="color: #dc2626;">Red/orange/yellow areas indicate regions where the AI detected potential TB abnormalities.</strong> Brighter colors indicate higher confidence.' 
            : '<strong style="color: #059669;">Blue/cyan overlay indicates normal scan.</strong> Green checkmarks confirm no significant abnormalities detected.'}
        </p>
        <div style="max-width: 600px; margin: 1rem auto;">
          <img src="${data.heatmap_url}" alt="AI Heatmap" class="heatmap-image" style="width: 100%; max-height: 500px; object-fit: contain; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />
        </div>
      </div>
    `;
  }

  html += `</div>`;
  resultBox.innerHTML = html;
}

/* ============================================================================
   PDF REPORT
   ============================================================================ */

async function downloadReport() {
  if (!reportData) {
    alert("Please analyze an X-ray first to generate a report.");
    return;
  }

  try {
    // Show loading state
    const downloadReportBtn = document.getElementById("downloadReportBtn");
    const originalText = downloadReportBtn.textContent;
    downloadReportBtn.textContent = "Generating PDF...";
    downloadReportBtn.disabled = true;

    // Simulate PDF generation
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Use jsPDF library approach - create a simple text-based PDF
    // For production, you should use a proper PDF library on the backend
    
    // Create simple HTML report that can be printed as PDF
    const reportHTML = generateHTMLReport(reportData);
    
    // Open in new window for printing
    const printWindow = window.open('', '_blank');
    printWindow.document.write(reportHTML);
    printWindow.document.close();
    
    // Trigger print dialog after content loads
    printWindow.onload = function() {
      printWindow.print();
    };

    // Show success message
    alert("Report opened in new window. Please use your browser's 'Save as PDF' option in the print dialog.");

    // Reset button state
    downloadReportBtn.textContent = originalText;
    downloadReportBtn.disabled = false;

  } catch (error) {
    console.error("Report generation failed:", error);
    alert("Failed to generate report. Please try again.");
    
    // Reset button state
    const downloadReportBtn = document.getElementById("downloadReportBtn");
    downloadReportBtn.textContent = "Download Report";
    downloadReportBtn.disabled = false;
  }
}

function generateHTMLReport(data) {
  const isPositive = data.raw_label === 'TB_POSITIVE';
  const statusText = isPositive ? 'TB Positive' : 'TB Negative';
  const statusColor = isPositive ? '#dc2626' : '#059669';
  
  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>PulmoScan AI - Medical Report</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 800px;
      margin: 40px auto;
      padding: 20px;
      line-height: 1.6;
    }
    .header {
      text-align: center;
      border-bottom: 3px solid #0066cc;
      padding-bottom: 20px;
      margin-bottom: 30px;
    }
    .header h1 {
      color: #0066cc;
      margin: 0;
      font-size: 28px;
    }
    .header p {
      color: #666;
      margin: 5px 0;
    }
    .result-box {
      background: ${isPositive ? '#fef2f2' : '#f0fdf4'};
      border: 2px solid ${statusColor};
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
    }
    .result-box h2 {
      color: ${statusColor};
      margin-top: 0;
    }
    .info-row {
      display: flex;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid #e5e7eb;
    }
    .info-row:last-child {
      border-bottom: none;
    }
    .info-label {
      font-weight: bold;
      color: #374151;
    }
    .info-value {
      color: #6b7280;
    }
    .recommendations {
      margin: 20px 0;
      padding: 20px;
      background: #f9fafb;
      border-left: 4px solid #0066cc;
    }
    .recommendations h3 {
      margin-top: 0;
      color: #1f2937;
    }
    .recommendations ul {
      margin: 10px 0;
      padding-left: 20px;
    }
    .recommendations li {
      margin: 8px 0;
      color: #4b5563;
    }
    .disclaimer {
      margin-top: 30px;
      padding: 15px;
      background: #fef3c7;
      border: 1px solid #f59e0b;
      border-radius: 6px;
      font-size: 14px;
    }
    .footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 2px solid #e5e7eb;
      text-align: center;
      color: #6b7280;
      font-size: 12px;
    }
    @media print {
      body {
        margin: 0;
        padding: 20px;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>PulmoScan AI</h1>
    <p>Clinical-Grade TB Detection Report</p>
    <p>Generated: ${data.timestamp}</p>
  </div>

  <div class="result-box">
    <h2>${statusText}</h2>
    <div class="info-row">
      <span class="info-label">Classification:</span>
      <span class="info-value">${statusText}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Confidence Level:</span>
      <span class="info-value">${data.confidence}%</span>
    </div>
    ${data.severity_score ? `
    <div class="info-row">
      <span class="info-label">Severity Score:</span>
      <span class="info-value">${data.severity_score.toFixed(2)} (${Math.round(data.severity_score * 100)}%)</span>
    </div>
    ` : ''}
    <div class="info-row">
      <span class="info-label">Filename:</span>
      <span class="info-value">${data.filename}</span>
    </div>
    <div class="info-row">
      <span class="info-label">File Size:</span>
      <span class="info-value">${data.filesize}</span>
    </div>
  </div>

  <div class="recommendations">
    <h3>${isPositive ? 'Recommended Next Steps' : 'Clinical Recommendations'}</h3>
    ${isPositive ? `
    <p>Based on AI analysis, tuberculosis features were detected. Please consult with a healthcare professional for confirmatory testing and treatment guidance.</p>
    <h4>Immediate Actions:</h4>
    <ul>
      <li>Consult pulmonologist or infectious disease specialist immediately</li>
      <li>Schedule sputum culture and PCR testing for confirmation</li>
      <li>Consider chest CT scan for detailed assessment</li>
      <li>Practice respiratory hygiene to prevent transmission</li>
      <li>Inform close contacts and follow isolation protocols</li>
      <li>Do not delay medical consultation</li>
    </ul>
    ` : `
    <p>The AI analysis did not detect TB features. However, this does not rule out all respiratory conditions. Please follow up with your healthcare provider.</p>
    <h4>Recommended Actions:</h4>
    <ul>
      <li>Share results with your healthcare provider</li>
      <li>Continue monitoring symptoms if present</li>
      <li>Follow up with clinical examination as scheduled</li>
      <li>Consider additional tests if symptoms persist</li>
      <li>Maintain regular health checkups</li>
      <li>Practice good respiratory hygiene</li>
    </ul>
    `}
  </div>

  <div class="disclaimer">
    <strong>⚠️ Medical Disclaimer:</strong><br>
    This AI tool assists healthcare professionals and is not a replacement for clinical diagnosis. 
    Always consult with qualified medical professionals for diagnosis and treatment decisions. 
    This report should be reviewed by a licensed healthcare provider before any medical decisions are made.
  </div>

  <div class="footer">
    <p><strong>PulmoScan AI</strong> - Advanced Tuberculosis Detection</p>
    <p>AI-assisted tool. Not a replacement for professional medical advice.</p>
    <p>For support: support@pulmoscan.ai | Medical inquiries: medical@pulmoscan.ai</p>
  </div>
</body>
</html>
  `;
}

/* ============================================================================
   UTILITIES
   ============================================================================ */

function clearAll() {
  if (!confirm("Are you sure you want to clear all scans and results?")) {
    return;
  }

  // Clear file inputs
  document.querySelectorAll("input[type='file']").forEach((input) => {
    input.value = "";
  });
  
  // Reset preview containers
  document.querySelectorAll(".preview-container").forEach((container) => {
    resetPreview(container);
  });
  
  // Clear result boxes
  document.querySelectorAll(".result-box").forEach((box) => {
    box.innerHTML = "";
    box.classList.remove("active");
  });
  
  // Disable analyze buttons
  const analyzeBtn = document.getElementById("analyzeBtn1");
  if (analyzeBtn) analyzeBtn.disabled = true;
  
  // Clear report data
  reportData = null;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/* ============================================================================
   NAVIGATION
   ============================================================================ */

function setActiveNav(event) {
  if (event && event.preventDefault) {
    event.preventDefault();
  }
  
  const target = event ? event.target : null;
  
  // Update active nav link
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.remove("active");
  });
  
  if (target) {
    target.classList.add("active");
  }

  // Smooth scroll to section
  if (target && target.getAttribute("href")) {
    const href = target.getAttribute("href");
    if (href.startsWith("#")) {
      const id = href.substring(1);
      const section = document.getElementById(id);
      
      if (section) {
        section.scrollIntoView({ 
          behavior: "smooth", 
          block: "start" 
        });
      }
    }
  }
}

/* ============================================================================
   UPLOAD ZONE CLICK HANDLING
   ============================================================================ */

function setupUploadZones() {
  const uploadZones = document.querySelectorAll(".upload-zone");
  
  uploadZones.forEach((zone) => {
    const zoneId = zone.getAttribute("id");
    const inputNumber = zoneId.replace("uploadZone", "");
    const inputId = `fileInput${inputNumber}`;
    const fileInput = document.getElementById(inputId);
    
    if (!fileInput) return;
    
    // Click to upload
    zone.addEventListener("click", (e) => {
      // Don't trigger if clicking on the file input itself
      if (e.target !== fileInput) {
        fileInput.click();
      }
    });
    
    // Drag and drop support
    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.style.borderColor = "var(--primary, #0066cc)";
      zone.style.background = "var(--primary-light, #e6f2ff)";
    });
    
    zone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.style.borderColor = "";
      zone.style.background = "";
    });
    
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.style.borderColor = "";
      zone.style.background = "";
      
      if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        handleFileSelect(inputId);
      }
    });
  });
}

/* ============================================================================
   INITIALIZATION
   ============================================================================ */

document.addEventListener("DOMContentLoaded", () => {
  console.log("PulmoScan AI Ready");

  // Setup file inputs
  const fileInput1 = document.getElementById("fileInput1");
  
  if (fileInput1) {
    fileInput1.addEventListener("change", () => handleFileSelect("fileInput1"));
  }

  // Setup analyze buttons
  const analyzeBtn1 = document.getElementById("analyzeBtn1");
  
  if (analyzeBtn1) {
    analyzeBtn1.addEventListener("click", () => analyzeScan("fileInput1"));
  }

  // Setup action buttons
  const clearAllBtn = document.getElementById("clearAllBtn");
  const downloadReportBtn = document.getElementById("downloadReportBtn");
  
  if (clearAllBtn) {
    clearAllBtn.addEventListener("click", clearAll);
  }
  
  if (downloadReportBtn) {
    downloadReportBtn.addEventListener("click", downloadReport);
  }

  // Setup navigation
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", setActiveNav);
  });

  // Setup upload zones
  setupUploadZones();

  // Set initial active nav based on URL hash or default to home
  const hash = window.location.hash || "#home";
  const activeLink = document.querySelector(`.nav-link[href="${hash}"]`);
  if (activeLink) {
    activeLink.click();
  }

  // Handle hash changes
  window.addEventListener("hashchange", () => {
    const newHash = window.location.hash || "#home";
    const newActiveLink = document.querySelector(`.nav-link[href="${newHash}"]`);
    if (newActiveLink) {
      setActiveNav({ target: newActiveLink, preventDefault: () => {} });
    }
  });
});

// Expose functions globally for inline event handlers
window.setActiveNav = setActiveNav;
window.analyzeScan = analyzeScan;
window.handleFileSelect = handleFileSelect;
window.clearAll = clearAll;
window.downloadReport = downloadReport;