import { TouchableOpacity, Text } from 'react-native';
import { Colors, Radius, Spacing } from '../lib/theme';

export const Button = ({ title, onPress }) => (
  <TouchableOpacity
    onPress={onPress}
    style={{
      backgroundColor: Colors.accent,
      paddingVertical: Spacing.sm + 6,
      paddingHorizontal: Spacing.md,
      borderRadius: Radius.md,
      alignItems: 'center',
      marginTop: Spacing.sm,
    }}
  >
    <Text style={{ color: '#fff', fontWeight: '600' }}>{title}</Text>
  </TouchableOpacity>
);