import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  FlatList,
  PermissionsAndroid,
  Platform,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import { financeAPI } from '../lib/api';
import { scanBankSms, type ParsedTransaction } from '../lib/smsScanner';
import { Colors, Radius, Spacing } from '../lib/theme';
import { GlassCard, LoadingSpinner, PrimaryButton, ScreenHeader, Tag } from '../components/ui';

type SelectableTransaction = ParsedTransaction & { selected: boolean; id: string };

const money = (v: number) =>
  `₹${Math.abs(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export default function SmsScannerScreen() {
  const router = useRouter();
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [transactions, setTransactions] = useState<SelectableTransaction[]>([]);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [done, setDone] = useState(false);

  const requestPermissionAndScan = useCallback(async () => {
    if (Platform.OS !== 'android') return;

    setScanning(true);
    setDone(false);
    setTransactions([]);

    try {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.READ_SMS,
        {
          title: 'Read SMS Permission',
          message:
            'FastTrade needs to read your SMS inbox to detect bank transaction alerts from HDFC, Axis, ICICI, SBI and other banks.',
          buttonPositive: 'Allow',
          buttonNegative: 'Deny',
        }
      );

      if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
        setPermissionDenied(true);
        setScanning(false);
        return;
      }

      setPermissionDenied(false);
      const parsed = await scanBankSms(300);

      const withIds: SelectableTransaction[] = parsed.map((tx, i) => ({
        ...tx,
        selected: true,
        id: `${tx.tran_date}-${i}`,
      }));

      setTransactions(withIds);
    } catch (e) {
      Alert.alert('Scan Failed', 'Could not read SMS. Make sure the app has SMS permission.');
    }

    setScanning(false);
    setDone(true);
  }, []);

  const toggleSelect = useCallback((id: string) => {
    setTransactions((prev) =>
      prev.map((tx) => (tx.id === id ? { ...tx, selected: !tx.selected } : tx))
    );
  }, []);

  const selectAll = useCallback(() =>
    setTransactions((prev) => prev.map((tx) => ({ ...tx, selected: true }))), []);

  const deselectAll = useCallback(() =>
    setTransactions((prev) => prev.map((tx) => ({ ...tx, selected: false }))), []);

  const importSelected = useCallback(async () => {
    const selected = transactions.filter((tx) => tx.selected);
    if (selected.length === 0) {
      Alert.alert('Nothing selected', 'Select at least one transaction to import.');
      return;
    }

    setImporting(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    try {
      await financeAPI.bulkCreateTransactions(
        selected.map(({ tran_date, description, debit, credit, balance, category, source }) => ({
          tran_date,
          description,
          debit,
          credit,
          balance,
          category,
          source,
        }))
      );
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setImporting(false);
      Alert.alert(
        '✅ Imported',
        `${selected.length} transaction${selected.length !== 1 ? 's' : ''} added to Finance.`,
        [{ text: 'Go to Finance', onPress: () => router.replace('/finance') }]
      );
    } catch (err: any) {
      setImporting(false);
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message || 'Could not import transactions.';
      Alert.alert('Import Failed', `Error: ${detail}`);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  }, [transactions, router]);

  const selectedCount = transactions.filter((tx) => tx.selected).length;

  if (Platform.OS !== 'android') {
    return (
      <View style={styles.root}>
        <SafeAreaView edges={['top']} style={styles.safe}>
          <ScreenHeader title="SMS Scanner" subtitle="Android only" onBack={() => router.back()} />
          <View style={styles.center}>
            <Text style={styles.notAvailable}>
              📱 SMS scanning is only available on Android devices.
            </Text>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScreenHeader
          title="Bank SMS Scanner"
          subtitle="Auto-detect transactions from bank SMS alerts"
          badge={<Tag label="ANDROID" color={Colors.green} bg={Colors.greenBg} />}
          onBack={() => router.back()}
        />

        <View style={styles.body}>
          {/* Scan button */}
          {!scanning && transactions.length === 0 && (
            <GlassCard style={styles.introCard}>
              <Ionicons name="mail-unread-outline" size={40} color={Colors.accent} style={styles.introIcon} />
              <Text style={styles.introTitle}>Scan Bank SMS</Text>
              <Text style={styles.introText}>
                FastTrade will read your SMS inbox and detect transaction alerts from HDFC, Axis,
                ICICI, SBI, Kotak and other Indian banks — including UPI payments and card
                transactions.
              </Text>
              <Text style={styles.introNote}>
                ⚠️ SMS data never leaves your device. Only parsed amounts are sent to your backend.
              </Text>
              {permissionDenied && (
                <Text style={styles.permError}>
                  SMS permission was denied. Please allow it in Android Settings → Apps → FastTrade → Permissions.
                </Text>
              )}
              <PrimaryButton
                title="Scan SMS Inbox"
                onPress={requestPermissionAndScan}
                style={{ marginTop: 16 }}
              />
            </GlassCard>
          )}

          {scanning && (
            <View style={styles.center}>
              <LoadingSpinner />
              <Text style={styles.scanningText}>Scanning SMS inbox…</Text>
            </View>
          )}

          {done && transactions.length === 0 && !scanning && (
            <GlassCard style={styles.introCard}>
              <Text style={styles.introTitle}>No Transactions Found</Text>
              <Text style={styles.introText}>
                No bank transaction SMS messages were detected. Make sure you have SMS alerts
                enabled with your bank.
              </Text>
              <PrimaryButton
                title="Scan Again"
                onPress={requestPermissionAndScan}
                variant="ghost"
                style={{ marginTop: 12 }}
              />
            </GlassCard>
          )}

          {transactions.length > 0 && (
            <>
              {/* Toolbar */}
              <View style={styles.toolbar}>
                <Text style={styles.toolbarCount}>
                  {transactions.length} found · {selectedCount} selected
                </Text>
                <View style={styles.toolbarActions}>
                  <TouchableOpacity onPress={selectAll} style={styles.toolbarBtn}>
                    <Text style={styles.toolbarBtnText}>All</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={deselectAll} style={styles.toolbarBtn}>
                    <Text style={styles.toolbarBtnText}>None</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={requestPermissionAndScan} style={styles.toolbarBtn}>
                    <Ionicons name="refresh-outline" size={14} color={Colors.accent} />
                  </TouchableOpacity>
                </View>
              </View>

              <FlatList
                data={transactions}
                keyExtractor={(item) => item.id}
                style={styles.list}
                contentContainerStyle={{ paddingBottom: 120 }}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    activeOpacity={0.85}
                    onPress={() => toggleSelect(item.id)}
                    style={[styles.txRow, item.selected && styles.txRowSelected]}
                  >
                    <View style={styles.txCheck}>
                      <Ionicons
                        name={item.selected ? 'checkbox' : 'square-outline'}
                        size={20}
                        color={item.selected ? Colors.accent : Colors.textMuted}
                      />
                    </View>
                    <View style={styles.txBody}>
                      <Text style={styles.txDesc} numberOfLines={1}>
                        {item.description}
                      </Text>
                      <Text style={styles.txMeta}>
                        {item.tran_date} · {item.category}
                      </Text>
                      {item.raw_sms ? (
                        <Text style={styles.txRaw} numberOfLines={1}>
                          {item.raw_sms}
                        </Text>
                      ) : null}
                    </View>
                    <View style={styles.txAmount}>
                      {item.debit > 0 ? (
                        <Text style={styles.txDebit}>-{money(item.debit)}</Text>
                      ) : (
                        <Text style={styles.txCredit}>+{money(item.credit)}</Text>
                      )}
                    </View>
                  </TouchableOpacity>
                )}
              />

              {/* Import bar */}
              <View style={styles.importBar}>
                <PrimaryButton
                  title={importing ? 'Importing…' : `Import ${selectedCount} Transaction${selectedCount !== 1 ? 's' : ''}`}
                  onPress={importSelected}
                  loading={importing}
                  disabled={selectedCount === 0 || importing}
                  variant="success"
                />
              </View>
            </>
          )}
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },
  safe: { flex: 1 },
  body: { flex: 1, padding: Spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  introCard: { alignItems: 'center', padding: Spacing.lg },
  introIcon: { marginBottom: 12 },
  introTitle: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary, marginBottom: 8, textAlign: 'center' },
  introText: { fontSize: 13, color: Colors.textSecondary, textAlign: 'center', lineHeight: 20, marginBottom: 8 },
  introNote: { fontSize: 11, color: Colors.textMuted, textAlign: 'center', fontStyle: 'italic', lineHeight: 16 },
  permError: { fontSize: 12, color: Colors.red, textAlign: 'center', marginTop: 8 },
  notAvailable: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', padding: Spacing.lg },
  scanningText: { fontSize: 14, color: Colors.textSecondary, marginTop: 12 },
  toolbar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  toolbarCount: { fontSize: 13, color: Colors.textSecondary, fontWeight: '600' },
  toolbarActions: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  toolbarBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
  },
  toolbarBtnText: { fontSize: 12, color: Colors.accent, fontWeight: '600' },
  list: { flex: 1 },
  txRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgGlass,
    marginBottom: 6,
  },
  txRowSelected: {
    borderColor: Colors.accent,
    backgroundColor: Colors.accentGlow,
  },
  txCheck: { marginRight: 10 },
  txBody: { flex: 1 },
  txDesc: { fontSize: 13, fontWeight: '600', color: Colors.textPrimary },
  txMeta: { fontSize: 11, color: Colors.textMuted, marginTop: 2 },
  txRaw: { fontSize: 10, color: Colors.textFaint, marginTop: 2, fontStyle: 'italic' },
  txAmount: { marginLeft: 8, alignItems: 'flex-end' },
  txDebit: { fontSize: 13, fontWeight: '700', color: Colors.red },
  txCredit: { fontSize: 13, fontWeight: '700', color: Colors.green },
  importBar: {
    position: 'absolute',
    bottom: 0,
    left: Spacing.lg,
    right: Spacing.lg,
    paddingBottom: Spacing.lg,
    paddingTop: 8,
    backgroundColor: Colors.bg,
  },
});
