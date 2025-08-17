export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR',
  FATAL = 'FATAL'
}

// Check if we're in a browser environment
const isBrowser = typeof window !== 'undefined' && typeof document !== 'undefined';

class Logger {
  private logLevel: LogLevel = LogLevel.INFO;
  private logToConsole: boolean = true;
  private logToFile: boolean = false;
  private logBuffer: string[] = [];
  private maxBufferSize: number = 1000;

  constructor() {
    // Only set up global error handlers in browser environment
    if (isBrowser) {
      this.setupGlobalErrorHandlers();
    }
  }

  private setupGlobalErrorHandlers() {
    if (!isBrowser) return;

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.error('Unhandled Promise Rejection', {
        reason: event.reason,
        stack: event.reason?.stack,
        message: event.reason?.message
      });
    });

    // Handle JavaScript errors
    window.addEventListener('error', (event) => {
      this.error('JavaScript Error', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error
      });
    });

    // Handle resource loading errors
    window.addEventListener('error', (event) => {
      if (event.target !== window) {
        this.error('Resource Loading Error', {
          target: event.target,
          type: event.type,
          message: event.message
        });
      }
    }, true);

    // Handle beforeunload events
    window.addEventListener('beforeunload', (event) => {
      this.info('Page Unloading', { timestamp: new Date().toISOString() });
    });

    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
      this.info('Page Visibility Changed', { 
        hidden: document.hidden,
        timestamp: new Date().toISOString()
      });
    });
  }

  private formatMessage(level: LogLevel, message: string, data?: any): string {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      level,
      message,
      data,
      url: isBrowser ? window.location.href : 'server',
      userAgent: isBrowser ? navigator.userAgent : 'server',
      memory: isBrowser && (performance as any).memory ? {
        usedJSHeapSize: Math.round((performance as any).memory.usedJSHeapSize / 1024 / 1024),
        totalJSHeapSize: Math.round((performance as any).memory.totalJSHeapSize / 1024 / 1024),
        jsHeapSizeLimit: Math.round((performance as any).memory.jsHeapSizeLimit / 1024 / 1024)
      } : null
    };

    const logString = JSON.stringify(logEntry, null, 2);
    
    // Add to buffer
    this.logBuffer.push(logString);
    if (this.logBuffer.length > this.maxBufferSize) {
      this.logBuffer.shift();
    }

    return logString;
  }

  private shouldLog(level: LogLevel): boolean {
    const levels = Object.values(LogLevel);
    const currentLevelIndex = levels.indexOf(this.logLevel);
    const messageLevelIndex = levels.indexOf(level);
    return messageLevelIndex >= currentLevelIndex;
  }

  private getColoredLevel(level: LogLevel): string {
    const colors = {
      [LogLevel.DEBUG]: '%cDEBUG%c',
      [LogLevel.INFO]: '%cINFO%c',
      [LogLevel.WARN]: '%cWARN%c',
      [LogLevel.ERROR]: '%cERROR%c',
      [LogLevel.FATAL]: '%cFATAL%c'
    };
    
    return colors[level] || level;
  }

  private log(level: LogLevel, message: string, data?: any) {
    if (!this.shouldLog(level)) return;

    const logString = this.formatMessage(level, message, data);
    const timestamp = new Date().toLocaleTimeString();
    const coloredLevel = this.getColoredLevel(level);

    if (this.logToConsole) {
      const consoleMethod = level === LogLevel.ERROR || level === LogLevel.FATAL ? 'error' :
                           level === LogLevel.WARN ? 'warn' :
                           level === LogLevel.INFO ? 'info' : 'log';
      
      // Enhanced console output with timestamps and colors
      console[consoleMethod](
        `%c[${timestamp}] ${coloredLevel}%c ${message}`,
        'color: #888; font-weight: bold;',
        'color: inherit;',
        data || ''
      );
    }

    // Send to backend if it's an error or fatal (only in browser)
    if ((level === LogLevel.ERROR || level === LogLevel.FATAL) && this.logToFile && isBrowser) {
      this.sendToBackend(level, message, data);
    }
  }

  private async sendToBackend(level: LogLevel, message: string, data?: any) {
    if (!isBrowser) return;
    
    try {
      await fetch('http://127.0.0.1:8080/v1/logs/frontend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          level,
          message,
          data,
          timestamp: new Date().toISOString(),
          url: window.location.href,
          userAgent: navigator.userAgent
        })
      });
    } catch (error) {
      // Fallback to console if backend is unreachable
      console.error('Failed to send log to backend:', error);
    }
  }

  debug(message: string, data?: any) {
    this.log(LogLevel.DEBUG, message, data);
  }

  info(message: string, data?: any) {
    this.log(LogLevel.INFO, message, data);
  }

  warn(message: string, data?: any) {
    this.log(LogLevel.WARN, message, data);
  }

  error(message: string, data?: any) {
    this.log(LogLevel.ERROR, message, data);
  }

  fatal(message: string, data?: any) {
    this.log(LogLevel.FATAL, message, data);
  }

  // Get all logs for debugging
  getLogs(): string[] {
    return [...this.logBuffer];
  }

  // Export logs for debugging
  exportLogs(): string {
    return this.logBuffer.join('\n');
  }

  // Clear logs
  clearLogs() {
    this.logBuffer = [];
  }

  // Set log level
  setLogLevel(level: LogLevel) {
    this.logLevel = level;
  }

  // Enable/disable console logging
  setConsoleLogging(enabled: boolean) {
    this.logToConsole = enabled;
  }

  // Enable/disable file logging
  setFileLogging(enabled: boolean) {
    this.logToFile = enabled;
  }
}

// Create singleton instance
export const logger = new Logger();

// Client-side only logger for Next.js components
export const clientLogger = isBrowser ? logger : {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  fatal: () => {},
  getLogs: () => [],
  exportLogs: () => '',
  clearLogs: () => {},
  setLogLevel: () => {},
  setConsoleLogging: () => {},
  setFileLogging: () => {}
};

export default isBrowser ? logger : clientLogger;
