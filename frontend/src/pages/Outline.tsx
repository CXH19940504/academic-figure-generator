import { useState, useCallback, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Loader2, Wand2, List, AlertCircle, Copy, Check, BookOpen, FileText, GraduationCap, Type } from 'lucide-react';
import api from '../lib/api';
import { getApiErrorMessage } from '../lib/apiError';

// 论文类型
const PAPER_TYPES = [
   { value: 1, label: '毕业论文', description: '本专科毕业论文，包含完整结构' },
   { value: 2, label: '期刊论文', description: '学术期刊投稿，注重研究方法' },
   { value: 3, label: '实习报告', description: '实习工作总结报告' },
   { value: 4, label: '调查报告', description: '社会/市场调查报告' },
];

// 学科分类 - 数据来源：教育部普通高等学校本科专业目录（2024年）
const SUBJECTS = [
   { code: '01', name: '哲学', categories: ['哲学', '逻辑学', '宗教学', '伦理学'] },
   { code: '02', name: '经济学', categories: ['经济学', '经济统计学', '财政学', '税收学', '金融学', '保险学', '投资学', '国际经济与贸易'] },
   { code: '03', name: '法学', categories: ['法学', '知识产权', '政治学与行政学', '国际政治', '社会学', '社会工作'] },
   { code: '04', name: '教育学', categories: ['教育学', '科学教育', '教育技术学', '学前教育', '小学教育', '特殊教育', '体育教育', '运动训练'] },
   { code: '05', name: '文学', categories: ['汉语言文学', '汉语言', '汉语国际教育', '英语', '日语', '新闻学', '广播电视学', '广告学', '传播学', '翻译', '商务英语'] },
   { code: '06', name: '历史学', categories: ['历史学', '世界史', '考古学', '文物与博物馆学', '文物保护技术', '文化遗产'] },
   { code: '07', name: '理学', categories: ['数学与应用数学', '信息与计算科学', '物理学', '应用物理学', '化学', '应用化学', '生物科学', '生物技术', '心理学', '应用心理学', '统计学', '应用统计学'] },
   { code: '08', name: '工学', categories: ['计算机科学与技术', '软件工程', '网络工程', '信息安全', '物联网工程', '电子信息工程', '通信工程', '自动化', '机械工程', '机械设计制造及其自动化', '电气工程及其自动化', '土木工程', '建筑学', '材料科学与工程', '化学工程与工艺'] },
   { code: '09', name: '农学', categories: ['农学', '园艺', '植物保护', '种子科学与工程', '设施农业科学与工程', '动物科学', '动物医学', '林学', '园林', '水产养殖学'] },
   { code: '10', name: '医学', categories: ['临床医学', '麻醉学', '医学影像学', '口腔医学', '预防医学', '中医学', '针灸推拿学', '药学', '药物制剂', '中药学', '护理学', '医学检验技术'] },
   { code: '12', name: '管理学', categories: ['工商管理', '市场营销', '会计学', '财务管理', '人力资源管理', '审计学', '公共事业管理', '行政管理', '劳动与社会保障', '土地资源管理', '信息管理与信息系统', '工程管理', '工程造价', '物流管理', '电子商务'] },
   { code: '13', name: '艺术学', categories: ['音乐表演', '音乐学', '舞蹈表演', '舞蹈学', '表演', '戏剧影视文学', '广播电视编导', '动画', '美术学', '绘画', '雕塑', '摄影', '书法学', '视觉传达设计', '环境设计', '产品设计', '服装与服饰设计', '数字媒体艺术'] },
];

// 学历层次
const DEGREES = [
   { value: '大专', label: '大专', defaultWords: 8000 },
   { value: '本科', label: '本科', defaultWords: 15000 },
   { value: '硕士', label: '硕士', defaultWords: 20000 },
   { value: '博士', label: '博士', defaultWords: 30000 },
   { value: 'MBA', label: 'MBA', defaultWords: 20000 },
];

// 字数选项
const WORD_COUNTS = [8000, 10000, 15000, 20000, 30000, 50000];

interface OutlineItem {
   level: number;
   title: string;
   order: number;
}

export function Outline() {
   // 项目状态
   const [projectId, setProjectId] = useState<string | null>(null);
   const [loadingProject, setLoadingProject] = useState(false);

   // 获取直接生成大纲的项目ID
   const fetchProject = async () => {
      if (loadingProject || projectId) return;
      setLoadingProject(true);
      try {
            const response = await api.get('/projects/by_name', {
               params: {
                  name: '直接生成大纲',
               },
            });
            if (response.data && response.data.id) {
               setProjectId(response.data.id);
            }
      } catch (error) {
            // 忽略错误，使用null项目ID
            setProjectId(null);
      } finally {
            setLoadingProject(false);
      }
   };

   // 表单状态
   const [title, setTitle] = useState('');
   const [paperType, setPaperType] = useState<number>(1);
   const [subjectCode, setSubjectCode] = useState<string>('06');
   const [degree, setDegree] = useState<string>('本科');
   const [wordCount, setWordCount] = useState<number>(15000);

   // 自定义prompt状态
   const [outlinePrompt, setOutlinePrompt] = useState('');
   const [templates, setTemplates] = useState<{ id: string; name: string }[]>([]);
   const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
   const [loadingTemplates, setLoadingTemplates] = useState(false);

   // 结果状态
   const [isGenerating, setIsGenerating] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [outlineResult, setOutlineResult] = useState<OutlineItem[] | null>(null);
   const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
   const [loadingDocuments, setLoadingDocuments] = useState(false);
   const [documentId, setDocumentId] = useState<string | null>(null);
   const [promptId, setPromptId] = useState<string | null>(null);

   // 获取项目文档
   const fetchDocumentId = async () => {
      if (!projectId) return;
      setLoadingDocuments(true);
      try {
         const response = await api.get(`/projects/${projectId}/documents`);
         const docs = response.data || [];
         
         // 如果有文档，获取第一个文档的 sections
         if (docs.length > 0) {
            const firstDoc = docs[0];
            setDocumentId(firstDoc.id || null);
            const docResponse = await api.get(`/documents/${firstDoc.id}`);
            if (docResponse.data) {
               if (docResponse.data.title) {
                  setTitle(docResponse.data.title);
               }
               if (docResponse.data.paper_type) {
                  setPaperType(docResponse.data.paper_type);
               }
               if (docResponse.data.subject_code) {
                  setSubjectCode(docResponse.data.subject_code);
               }
               if (docResponse.data.file_size_bytes) {
                  setWordCount(docResponse.data.file_size_bytes);
               }
               if (docResponse.data.template_id) {
                  setSelectedTemplate(docResponse.data.template_id);
               }
            } 
         }
      } catch (error) {
         console.error('获取文档列表失败:', error);
         setDocumentId(null);
      } finally {
         setLoadingDocuments(false);
      }
   };

   // 获取文档的 prompts
   const fetchDocumentPrompts = async () => {
      if (!documentId) return;
      try {
         const response = await api.get(`/documents/${documentId}/prompts`, {
            params: {
               material_type: 1,
            },
         });
         const prompts = response.data || [];
         if (prompts.length > 0) {
            const latestPrompt = prompts[0];
            const promptContent = latestPrompt.active_prompt || '';
            setOutlinePrompt(promptContent);
            setPromptId(latestPrompt.id || null);
            setIsGenerating(latestPrompt.generate_status === 'generating');
         } else {
            setOutlinePrompt('');
            setPromptId(null);
            setIsGenerating(false);
         }
      } catch (error) {
         console.error('获取文档 prompts 失败:', error);
      }
   };

   const fetchDocumentSections = async () => {
      if (!documentId) return;
      try {
         const response = await api.get(`/documents/${documentId}/sections`);
         setOutlineResult(response.data.sections || []);
      } catch (error) {
         console.error('获取文档 sections 失败:', error);
         setOutlineResult(null);
      }
   };

   // 监听 projectId 变化
   useEffect(() => {
      if (!projectId) return;
      fetchDocumentId();
      fetchDocumentPrompts();
   }, [projectId]);

   // 监听 promptId 变化
   useEffect(() => {
      if (!promptId) return;
      if (isGenerating === false) {
         fetchDocumentSections();
         return;
      }
      const interval = setInterval(() => { fetchDocumentPrompts(); }, 5000);
      return () => clearInterval(interval);
   }, [promptId]);

   // 挂载时获取项目ID
   useEffect(() => {
      fetchProject();
   }, []);

   // 项目ID就绪后加载模板列表
   useEffect(() => {
      if (!projectId) return;

      const loadTemplates = async () => {
         setLoadingTemplates(true);
         try {
            const response = await api.get('/templates');
            const templatesData = response.data || [];
            setTemplates(templatesData);
            if (templatesData.length > 0 && !selectedTemplate) {
               setSelectedTemplate(String(templatesData[0].id));
            }
         } catch {
            setTemplates([]);
         } finally {
            setLoadingTemplates(false);
         }
      };
      loadTemplates();
   }, [projectId]);

   // 学历变更时更新默认字数
   const handleDegreeChange = (newDegree: string) => {
      setDegree(newDegree);
      const degreeObj = DEGREES.find(d => d.value === newDegree);
      if (degreeObj) {
         setWordCount(degreeObj.defaultWords);
      }
   };

   // 使用自定义prompt重新生成大纲
   const handleGenerateDirect = async () => {
      if (!title.trim() || !outlinePrompt.trim()) {
         setError('请输入论文标题和自定义prompt');
         return;
      }

      setIsGenerating(true);
      setOutlineResult(null);
      setError(null);

      try {
         const response = await api.post('/outline/generate-direct', {
            project_id: projectId,  // 直接生成模式，不关联项目
            document_id: documentId,
            prompt_id: promptId,
            title,
            outline_prompt: outlinePrompt,
         });
         // 如果是直接生成模式，且返回了 document_id，更新 documentId
         // 否则，仍然显示旧的大纲
         if (response.data.document_id !== documentId) {
            setDocumentId(response.data.document_id);
            setPromptId(response.data.prompt_id);
         } else {
            fetchDocumentSections();
         }

      } catch (e: any) {
         console.error(e);
         const msg = getApiErrorMessage(e, '请求失败，请检查网络连接');
         setError(msg);
      } finally {
         setIsGenerating(false);
      }
   };

   // 生成大纲
   const handleGenerate = async () => {
      if (!title.trim()) {
         setError('请输入论文标题');
         return;
      }
      if (title.length < 10) {
         setError('论文标题至少需要10个字符');
         return;
      }
      if (title.length > 500) {
         setError('论文标题不能超过500个字符');
         return;
      }

      setOutlineResult(null);
      setError(null);

      try {
         // 第一步：创建 Prompt 并获取 system_prompt
         const promptResponse = await api.post('/outline/prompt', {
            project_id: projectId,
            document_id: documentId,
            prompt_id: promptId,
            title,
            paper_type: paperType,
            subject_code: subjectCode,
            degree,
            word_count: wordCount,
            template_id: selectedTemplate,
         });

         const { prompt_id, system_prompt, document_id } = promptResponse.data;
         
         // 将 system_prompt 渲染到 outlinePrompt
         setOutlinePrompt(system_prompt);
         setPromptId(prompt_id);
         setDocumentId(document_id);
         setIsGenerating(true);

         // 第二步：使用 prompt_id 生成大纲
         const generateResponse = await api.post(`/outline/${prompt_id}/generate`);

         // 根据返回的 document_id 获取大纲详情
         if (generateResponse.data.document_id) {
            const docResponse = await api.get(`/documents/${generateResponse.data.document_id}`);
            setOutlineResult(docResponse.data.sections || []);
         } else {
            setOutlineResult(generateResponse.data.sections || []);
         }
      } catch (e: any) {
         console.error(e);
         const msg = getApiErrorMessage(e, '请求失败，请检查网络连接');
         setError(msg);
      } finally {
         setIsGenerating(false);
      }
   };

   // 复制单个大纲条目
   const handleCopyOutline = useCallback(async (text: string, index: number) => {
      try {
         await navigator.clipboard.writeText(text);
         setCopiedIndex(index);
         setTimeout(() => setCopiedIndex(null), 2000);
      } catch {
         const textarea = document.createElement('textarea');
         textarea.value = text;
         document.body.appendChild(textarea);
         textarea.select();
         document.execCommand('copy');
         document.body.removeChild(textarea);
         setCopiedIndex(index);
         setTimeout(() => setCopiedIndex(null), 2000);
      }
   }, []);

   // 复制全部大纲
   const handleCopyAll = useCallback(async () => {
      if (!outlineResult) return;
      const text = outlineResult.map(item =>
         '  '.repeat(item.level - 1) + `${item.order}. ${item.title}`
      ).join('\n');
      try {
         await navigator.clipboard.writeText(text);
         setCopiedIndex(-1);
         setTimeout(() => setCopiedIndex(-1), 2000);
      } catch {
         const textarea = document.createElement('textarea');
         textarea.value = text;
         document.body.appendChild(textarea);
         textarea.select();
         document.execCommand('copy');
         document.body.removeChild(textarea);
         setCopiedIndex(-1);
         setTimeout(() => setCopiedIndex(-1), 2000);
      }
   }, [outlineResult]);

   // 获取大纲样式
   const getLevelStyles = (level: number) => {
      const styles: Record<number, { indent: string; fontSize: string; fontWeight: string }> = {
         1: { indent: 'pl-0', fontSize: 'text-base', fontWeight: 'font-semibold' },
         2: { indent: 'pl-4', fontSize: 'text-sm', fontWeight: 'font-medium' },
         3: { indent: 'pl-8', fontSize: 'text-sm', fontWeight: 'font-normal' },
      };
      return styles[level] || styles[3];
   };

   const getLevelLabel = (level: number) => {
      const labels: Record<number, string> = { 1: '章', 2: '节', 3: '小节' };
      return labels[level] || '条';
   };

   // 获取当前学科名称
   const currentSubject = SUBJECTS.find(s => s.code === subjectCode);

   return (
      <div className="max-w-6xl mx-auto space-y-6">
         <div>
            <h1 className="text-3xl font-bold tracking-tight">论文大纲生成</h1>
            <p className="text-muted-foreground mt-1">输入论文信息，AI智能生成结构化论文大纲。</p>
         </div>

         {error && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive text-sm">
               <AlertCircle className="h-4 w-4 shrink-0" />
               <span>{error}</span>
            </div>
         )}

         <div className="grid lg:grid-cols-5 gap-6">
            {/* 左侧配置面板 */}
            <div className="lg:col-span-3 space-y-4">
               <Card>
                  <CardHeader>
                     <CardTitle className="flex items-center gap-2">
                        <BookOpen className="w-5 h-5" />
                        基本信息
                     </CardTitle>
                     <CardDescription>填写论文基本信息，AI将根据这些参数生成专业大纲</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                     {/* 论文标题 */}
                     <div className="space-y-2">
                        <label className="text-sm font-medium flex items-center gap-2">
                           <FileText className="w-4 h-4" />
                           论文标题 <span className="text-destructive">*</span>
                        </label>
                        <Input
                           placeholder="请输入论文标题，例如：基于深度学习的医学影像诊断研究"
                           value={title}
                           onChange={e => setTitle(e.target.value)}
                           maxLength={200}
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                           <span>建议10-50字，清晰表达研究主题</span>
                           <span>{title.length}/200</span>
                        </div>
                     </div>

                     {/* 论文类型 */}
                     <div className="space-y-2">
                        <label className="text-sm font-medium flex items-center gap-2">
                           <Type className="w-4 h-4" />
                           论文类型 <span className="text-destructive">*</span>
                        </label>
                        <Select value={String(paperType)} onValueChange={v => setPaperType(Number(v))}>
                           <SelectTrigger>
                              <SelectValue />
                           </SelectTrigger>
                           <SelectContent>
                              {PAPER_TYPES.map(type => (
                                 <SelectItem key={type.value} value={String(type.value)}>
                                    <div className="flex flex-col items-start">
                                       <span>{type.label}</span>
                                       <span className="text-xs text-muted-foreground">{type.description}</span>
                                    </div>
                                 </SelectItem>
                              ))}
                           </SelectContent>
                        </Select>
                     </div>

                     {/* 学科选择 */}
                     <div className="space-y-2">
                        <label className="text-sm font-medium">学科分类</label>
                        <Select value={subjectCode} onValueChange={setSubjectCode}>
                           <SelectTrigger>
                              <SelectValue />
                           </SelectTrigger>
                           <SelectContent>
                              {SUBJECTS.map(subject => (
                                 <SelectItem key={subject.code} value={subject.code}>
                                    {subject.name}
                                 </SelectItem>
                              ))}
                           </SelectContent>
                        </Select>
                        {currentSubject && (
                           <div className="text-xs text-muted-foreground">
                              包含：{currentSubject.categories.join('、')}
                           </div>
                        )}
                     </div>
                  </CardContent>
               </Card>

               <Card>
                  <CardHeader>
                     <CardTitle className="flex items-center gap-2">
                        <GraduationCap className="w-5 h-5" />
                        参数配置
                     </CardTitle>
                     <CardDescription>根据学历和要求调整大纲详细程度</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                     {/* 学历层次 */}
                     <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                           <label className="text-sm font-medium">学历层次</label>
                           <Select value={degree} onValueChange={handleDegreeChange}>
                              <SelectTrigger>
                                 <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                 {DEGREES.map(d => (
                                    <SelectItem key={d.value} value={d.value}>
                                       {d.label}
                                    </SelectItem>
                                 ))}
                              </SelectContent>
                           </Select>
                        </div>

                        <div className="space-y-2">
                           <label className="text-sm font-medium">目标字数</label>
                           <Select value={String(wordCount)} onValueChange={v => setWordCount(Number(v))}>
                              <SelectTrigger>
                                 <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                 {WORD_COUNTS.map(count => (
                                    <SelectItem key={count} value={String(count)}>
                                       {count >= 10000 ? `${count / 10000}万字` : `${count}字`}
                                    </SelectItem>
                                 ))}
                              </SelectContent>
                           </Select>
                        </div>
                     </div>

                     {/* 排版模板 */}
                     <div className="space-y-2">
                        <label className="text-sm font-medium">排版模板（可选）</label>
                        <Select
                           value={selectedTemplate ?? 'none'}
                           onValueChange={v => setSelectedTemplate(v === 'none' ? null : v)}
                           disabled={loadingTemplates}
                        >
                           <SelectTrigger>
                              <SelectValue placeholder={loadingTemplates ? '加载中...' : '选择模板'} />
                           </SelectTrigger>
                           <SelectContent>
                              <SelectItem value="none">不使用模板</SelectItem>
                              {templates.map(t => (
                                 <SelectItem key={t.id} value={String(t.id)}>
                                    {t.name}
                                 </SelectItem>
                              ))}
                           </SelectContent>
                        </Select>
                     </div>
                  </CardContent>
               </Card>

               {/* 生成大纲的prompt */}
               <Card>
                  <CardHeader>
                     <CardTitle>生成大纲的prompt</CardTitle>
                     <CardDescription>修改prompt，帮助AI更准确地生成大纲</CardDescription>
                  </CardHeader>
                  <CardContent>
                     <Textarea
                        placeholder="尚未设置prompt..."
                        className="min-h-[200px]"
                        value={outlinePrompt}
                        onChange={e => setOutlinePrompt(e.target.value)}
                     />
                  </CardContent>
                  <CardFooter className="border-t pt-4 flex gap-2">
                     <Button
                        id="generate-outline"
                        className="flex-1"
                        size="sm"
                        onClick={handleGenerate}
                        disabled={isGenerating || !title.trim()}
                     >
                        {isGenerating ? (
                           <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> 生成中...</>
                        ) : (
                           <><Wand2 className="w-4 h-4 mr-1" /> 生成大纲</>
                        )}
                     </Button>
                     <Button
                        id="generate-direct"
                        variant="outline"
                        className="flex-1"
                        size="sm"
                        onClick={handleGenerateDirect}
                        disabled={!title.trim() || !outlinePrompt.trim()}
                     >
                        {isGenerating ? (
                           <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> 生成中...</>
                        ) : (
                           <><Wand2 className="w-4 h-4 mr-1" /> 使用修改的prompt</>
                        )}
                     </Button>
                  </CardFooter>
               </Card>
            </div>

            {/* 右侧结果面板 */}
            <div className="lg:col-span-2 space-y-4">
               <Card className="sticky top-6">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0">
                     <div>
                        <CardTitle className="flex items-center gap-2">
                           <List className="w-5 h-5" />
                           生成结果
                        </CardTitle>
                        <CardDescription>AI 生成的大纲</CardDescription>
                     </div>
                     {outlineResult && outlineResult.length > 0 && (
                        <Button variant="outline" size="sm" onClick={handleCopyAll}>
                           {copiedIndex === -1 ? (
                              <><Check className="w-4 h-4 mr-1" /> 已复制</>
                           ) : (
                              <><Copy className="w-4 h-4 mr-1" /> 复制全部</>
                           )}
                        </Button>
                     )}
                  </CardHeader>
                  <CardContent className="min-h-[600px] bg-muted/10 border-t">
                     {isGenerating || loadingDocuments ? (
                        <div className="flex items-center justify-center h-full">
                           <div className="text-center">
                              <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                              <p className="text-sm text-muted-foreground mt-4">
                                 {loadingDocuments ? '正在加载文档...' : 'AI 正在分析并生成大纲...'}
                              </p>
                              <p className="text-xs text-muted-foreground/60 mt-1">
                                 {loadingDocuments ? '加载历史生成记录' : '根据您提供的信息构建论文结构'}
                              </p>
                           </div>
                        </div>
                     ) : outlineResult && outlineResult.length > 0 ? (
                        <div className="space-y-1 overflow-auto max-h-[500px] p-2">
                           {outlineResult.map((item, index) => {
                              const styles = getLevelStyles(item.level);
                              return (
                                 <div
                                    key={index}
                                    className={`flex items-start gap-2 p-2 rounded-md hover:bg-background/80 transition-colors group ${styles.indent}`}
                                 >
                                    <span className={`${styles.fontWeight} ${styles.fontSize} text-foreground flex-1 leading-relaxed`}>
                                       <span className="inline-block w-6 text-muted-foreground/60 font-normal">{item.order}.</span>
                                       {item.title}
                                    </span>
                                    <Button
                                       variant="ghost"
                                       size="sm"
                                       className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
                                       onClick={() => handleCopyOutline(`${item.order}. ${item.title}`, index)}
                                    >
                                       {copiedIndex === index ? (
                                          <Check className="w-3 h-3 text-green-500" />
                                       ) : (
                                          <Copy className="w-3 h-3 text-muted-foreground" />
                                       )}
                                    </Button>
                                    <span className={`text-xs px-1 py-0.5 rounded bg-muted text-muted-foreground ${styles.fontWeight}`}>
                                       {getLevelLabel(item.level)}
                                    </span>
                                 </div>
                              );
                           })}
                        </div>
                     ) : (
                        <div className="flex items-center justify-center h-full">
                           <div className="text-center">
                              <List className="h-12 w-12 text-muted-foreground/50 mx-auto" />
                              <p className="text-sm text-muted-foreground mt-4">暂无生成的大纲</p>
                              <p className="text-xs text-muted-foreground/60 mt-1">请填写论文信息后点击生成</p>
                           </div>
                        </div>
                     )}
                  </CardContent>
                  {outlineResult && outlineResult.length > 0 && (
                     <CardFooter className="bg-muted/30 pt-4 border-t">
                        <div className="flex items-center justify-between w-full text-sm text-muted-foreground">
                           <span>共 {outlineResult.length} 个条目</span>
                           <span>支持 {Math.max(...outlineResult.map(item => item.level))} 级大纲</span>
                        </div>
                     </CardFooter>
                  )}
               </Card>
            </div>
         </div>
      </div>
   );
}

